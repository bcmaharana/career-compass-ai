"""Groq provider adapter — implements LLMProviderInterface against
Groq's hosted, OpenAI-compatible Chat Completions API.

No official SDK dependency pulled in for this — Groq's API is a plain,
stable, OpenAI-shaped REST endpoint, the same "no SDK, use httpx"
approach already used for Ollama (app/adapters/ai_providers/ollama_provider.py)
and the quote-of-the-day adapter. Response shape differs from both
existing providers (Anthropic's own shape, Ollama's own shape) — this
is the standard OpenAI chat-completion JSON: `choices[0].message.content`,
`usage.prompt_tokens`/`usage.completion_tokens`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.adapters.ai_providers.errors import AIProviderError
from app.ai_platform.llm_service.provider_interface import LLMRequest, LLMResponse
from app.core.config import Settings

_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# Hosted + fast (280-560 tokens/sec on Groq's LPU hardware per their own
# docs) — no reason for Ollama's generous 600s default here. Still
# overridable per-request via LLMRequest.timeout_seconds.
_REQUEST_TIMEOUT_SECONDS = 60.0
# Verified live by directly probing the Chat Completions API with this
# project's own key: `llama-3.3-70b-versatile` itself advertises a
# 131072-token context window and a 32768-token max_completion_tokens
# (per GET /openai/v1/models/llama-3.3-70b-versatile) — but this
# specific free "on_demand" org sits behind a much smaller enforced
# cap: "Rate limit reached ... tokens per minute (TPM): Limit 12000".
# A resume-extraction request with a long prompt (~3000 input tokens of
# instructions alone) plus max_tokens=8192 sums to ~12200 and gets
# rejected outright (HTTP 413) before the model ever runs — this is a
# hard per-request ceiling on THIS free tier, not a rate-limit-through-
# repeated-use problem, and not something raising a shared
# LLMRequest.max_tokens constant can route around, since Anthropic/
# Ollama have no equivalent limit and shouldn't be starved to
# accommodate it. Clamped defensively here, in the adapter that
# actually knows about Groq's quirk, rather than in any caller.
_SAFE_TOTAL_TOKEN_BUDGET = 11400  # 600-token margin under the real 12000 TPM cap
_MIN_CLAMPED_MAX_TOKENS = 512
# Rough chars-per-token heuristic (no tokenizer dependency pulled in for
# this) — good enough for a defensive clamp, not exact accounting;
# the margin above absorbs the estimation error. Raised from
# 4 to 4.4 after a real resume_extraction prompt showed Groq's actual
# reported prompt_tokens running noticeably below the old estimate
# (7147 real vs ~8291 estimated at 4 chars/token, a ~4.64 real ratio) —
# the old, too-conservative estimate was silently stealing ~1000 tokens
# of genuinely available output room on every request.
#
# Raised again 4.4 -> 4.6, and margin tightened 1000 -> 600, on
# 2026-08-07 after the prompt template's growth (17K chars of worked
# examples, up from a much leaner version) pushed a real "medium"
# 10-role resume into this exact truncation failure: the old settings
# clamped max_tokens to 4096 (11000 - an estimated 6904 against a real
# 6581), and the model needed 4554 completion tokens for a complete,
# valid extraction — verified live via a direct Groq call with
# max_tokens=5300 outside the app (finish_reason: "stop", all 6
# sections populated, 11135 total tokens against the real 12000 cap).
# 4.6 stays just under the real ~4.616 chars/token ratio measured on
# that same call (30382 rendered chars / 6581 real prompt tokens),
# tight enough that the estimate now overestimates by only ~24 tokens
# instead of ~320. Margin dropped from 1000 to 600 since the tighter
# ratio above already removes most of the estimation slack that
# 1000 tokens existed to absorb — a longer or more unusual resume can
# still hit this same failure mode again (Groq's 12000 TPM hard cap is
# fixed and not something this budget math can route around indefinitely
# as the prompt template keeps growing), but this specific case is
# fixed with real margin still in hand (12000 - 11135 = 865 tokens
# unused on the verifying call).
_CHARS_PER_TOKEN_ESTIMATE = 4.6


def _format_wait(retry_after_seconds: str | None) -> str:
    """Groq's `retry-after` header is always raw seconds, whether the
    underlying limit is a short per-minute window or the much longer
    per-day one (see the 429 handler above) — "9022 seconds" means
    nothing to a user, so this renders whichever unit reads naturally.
    """
    if retry_after_seconds is None:
        return "a little while"
    try:
        seconds = float(retry_after_seconds)
    except ValueError:
        return "a little while"
    if seconds < 120:
        return f"{round(seconds)} seconds"
    minutes = seconds / 60
    if minutes < 120:
        return f"{round(minutes)} minutes"
    hours = minutes / 60
    return f"{round(hours, 1)} hours"


@dataclass(slots=True, frozen=True)
class GroqRateLimitSnapshot:
    """The most recently observed values of Groq's rate-limit headers.

    Verified against Groq's own docs (console.groq.com/docs/rate-limits):
    `x-ratelimit-limit-requests`/`-remaining-requests` track the DAILY
    request cap, `x-ratelimit-limit-tokens`/`-remaining-tokens` track the
    PER-MINUTE token cap (the two buckets `_SAFE_TOTAL_TOKEN_BUDGET`
    above and `_format_wait`'s 429 handling were already reasoning
    about separately) — Groq exposes no separate per-minute-request or
    per-day-token pair. The two `reset_*` fields are duration strings
    as Groq sends them (e.g. "2m59.56s"), not seconds — left unparsed
    rather than guessing a fragile format, since the only thing that
    matters here is showing the user Groq's own number.
    """

    limit_requests: int | None
    remaining_requests: int | None
    reset_requests: str | None
    limit_tokens: int | None
    remaining_tokens: int | None
    reset_tokens: str | None
    observed_at: datetime


# In-memory only, same as the auth store and every other ephemeral piece
# of state in this codebase (no job queue/cache layer exists to persist
# this) — resets on backend restart. Populated passively off headers
# already present on every real Groq response (success or 429), never by
# a dedicated poll: check_groq() in app/adapters/system_status/checkers.py
# deliberately avoids spending real quota just to feed a dashboard.
_last_rate_limit_snapshot: GroqRateLimitSnapshot | None = None


def get_last_rate_limit_snapshot() -> GroqRateLimitSnapshot | None:
    return _last_rate_limit_snapshot


def _capture_rate_limit_snapshot(headers: httpx.Headers) -> None:
    global _last_rate_limit_snapshot

    def _int(key: str) -> int | None:
        raw = headers.get(key)
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    _last_rate_limit_snapshot = GroqRateLimitSnapshot(
        limit_requests=_int("x-ratelimit-limit-requests"),
        remaining_requests=_int("x-ratelimit-remaining-requests"),
        reset_requests=headers.get("x-ratelimit-reset-requests"),
        limit_tokens=_int("x-ratelimit-limit-tokens"),
        remaining_tokens=_int("x-ratelimit-remaining-tokens"),
        reset_tokens=headers.get("x-ratelimit-reset-tokens"),
        observed_at=datetime.now(UTC),
    )


class GroqProvider:
    """Implements LLMProviderInterface against Groq's Chat Completions API."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.groq_api_key

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self._api_key:
            raise AIProviderError(
                "Groq API key is not configured (GROQ_API_KEY).",
                code="AI_PROVIDER_NOT_CONFIGURED",
            )

        estimated_prompt_tokens = int(len(request.rendered_prompt) // _CHARS_PER_TOKEN_ESTIMATE)
        clamped_max_tokens = max(
            _MIN_CLAMPED_MAX_TOKENS,
            min(request.max_tokens, _SAFE_TOTAL_TOKEN_BUDGET - estimated_prompt_tokens),
        )

        body: dict[str, object] = {
            "model": request.model_name,
            "messages": [{"role": "user", "content": request.rendered_prompt}],
            "max_tokens": clamped_max_tokens,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        timeout_seconds = request.timeout_seconds or _REQUEST_TIMEOUT_SECONDS

        started_at = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    _API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=body,
                )
                # Captured before raise_for_status() so a 429 updates the
                # snapshot too - that's the response most worth seeing.
                _capture_rate_limit_snapshot(response.headers)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            # httpx's timeout exceptions stringify to an empty message by
            # default (str(exc) == "") — same gotcha OllamaProvider's own
            # adapter already needed a dedicated branch for.
            raise AIProviderError(
                f"Groq didn't respond within {timeout_seconds:.0f}s.",
                code="AI_PROVIDER_REQUEST_FAILED",
            ) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                # This account's free tier enforces multiple separate caps
                # (verified live via GET .../models response headers) — a
                # short-window 12000-tokens/minute limit (see
                # _SAFE_TOTAL_TOKEN_BUDGET above, resets in seconds) AND a
                # much longer 1000-requests/day limit. A 429 can come from
                # either, and Groq's own `retry-after` header (seconds) is
                # the only reliable way to tell them apart — a live test
                # here returned as little as under a minute (the token
                # window) and, later the same day after enough cumulative
                # requests, over 9000 seconds (the daily window). Never
                # claim a specific window in the message text since either
                # is possible; just relay Groq's own number, formatted
                # readably rather than as raw seconds.
                retry_after_raw = exc.response.headers.get("retry-after")
                wait_hint = f" Try again in about {_format_wait(retry_after_raw)}."
                raise AIProviderError(
                    "Groq's free-tier rate limit was reached." + wait_hint,
                    code="AI_PROVIDER_RATE_LIMITED",
                ) from exc
            raise AIProviderError(
                f"Groq request failed: {exc}", code="AI_PROVIDER_REQUEST_FAILED"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                f"Groq request failed: {exc}", code="AI_PROVIDER_REQUEST_FAILED"
            ) from exc
        latency_ms = (time.perf_counter() - started_at) * 1000

        text = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})

        return LLMResponse(
            text=text,
            prompt_version_id=request.prompt_version_id,
            model_version_id=request.model_version_id,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
        )
