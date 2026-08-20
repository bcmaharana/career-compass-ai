"""Unit tests for GroqProvider's defensive max_tokens clamp
(_clamp_max_tokens) — pure math, no httpx/network involved. This is
the first unit test for this adapter; GroqProvider.generate() itself
makes a real HTTP call and isn't exercised here.
"""

from __future__ import annotations

import pytest

from app.adapters.ai_providers.groq_provider import (
    _ABSOLUTE_MIN_MAX_TOKENS,
    _CHARS_PER_TOKEN_ESTIMATE,
    _MIN_CLAMPED_MAX_TOKENS,
    _SAFE_TOTAL_TOKEN_BUDGET,
    _clamp_max_tokens,
)

pytestmark = pytest.mark.unit


class TestClampMaxTokens:
    def test_small_prompt_keeps_the_requested_max_tokens(self) -> None:
        clamped = _clamp_max_tokens(rendered_prompt_len=1000, requested_max_tokens=1500)
        assert clamped == 1500

    def test_large_prompt_reduces_max_tokens_to_stay_under_budget(self) -> None:
        # A prompt that eats most of the budget but still leaves room
        # for the _MIN_CLAMPED_MAX_TOKENS floor.
        prompt_len = int((_SAFE_TOTAL_TOKEN_BUDGET - 1000) * _CHARS_PER_TOKEN_ESTIMATE)
        clamped = _clamp_max_tokens(rendered_prompt_len=prompt_len, requested_max_tokens=8192)
        estimated_prompt_tokens = int(prompt_len // _CHARS_PER_TOKEN_ESTIMATE)
        assert clamped == _SAFE_TOTAL_TOKEN_BUDGET - estimated_prompt_tokens
        assert estimated_prompt_tokens + clamped <= _SAFE_TOTAL_TOKEN_BUDGET

    def test_huge_prompt_stays_under_the_real_groq_cap_where_the_old_code_did_not(self) -> None:
        # Confirmed live (2026-08-19): the old code's
        # max(_MIN_CLAMPED_MAX_TOKENS, ...) shape forced max_tokens back
        # up to a fixed 512 even when the prompt alone had already eaten
        # past (_SAFE_TOTAL_TOKEN_BUDGET - _MIN_CLAMPED_MAX_TOKENS) —
        # pushing the real total over Groq's hard 12000 TPM cap and
        # producing a genuine 413 on a real, large resume-extraction
        # request. This prompt size reproduces exactly that: under the
        # OLD logic, estimated_prompt_tokens + 512 would land at 12012,
        # over the real 12000 cap. The fixed clamp must stay under it.
        _REAL_GROQ_TPM_CAP = 12000
        estimated_prompt_tokens_target = 11500
        prompt_len = int(estimated_prompt_tokens_target * _CHARS_PER_TOKEN_ESTIMATE)
        estimated_prompt_tokens = int(prompt_len // _CHARS_PER_TOKEN_ESTIMATE)
        assert estimated_prompt_tokens > _SAFE_TOTAL_TOKEN_BUDGET - _MIN_CLAMPED_MAX_TOKENS
        old_buggy_total = estimated_prompt_tokens + _MIN_CLAMPED_MAX_TOKENS
        assert old_buggy_total > _REAL_GROQ_TPM_CAP  # the bug this reproduces

        clamped = _clamp_max_tokens(rendered_prompt_len=prompt_len, requested_max_tokens=8192)

        assert clamped == _ABSOLUTE_MIN_MAX_TOKENS
        assert clamped < _MIN_CLAMPED_MAX_TOKENS
        assert estimated_prompt_tokens + clamped < _REAL_GROQ_TPM_CAP

    def test_requested_max_tokens_below_the_available_budget_is_left_untouched(self) -> None:
        clamped = _clamp_max_tokens(rendered_prompt_len=4000, requested_max_tokens=200)
        assert clamped == 200

    def test_result_never_goes_below_the_absolute_minimum(self) -> None:
        # An extreme, pathological prompt length — even here the clamp
        # must return a usable (if small) positive value, not zero or
        # negative.
        prompt_len = int(_SAFE_TOTAL_TOKEN_BUDGET * _CHARS_PER_TOKEN_ESTIMATE * 3)
        clamped = _clamp_max_tokens(rendered_prompt_len=prompt_len, requested_max_tokens=8192)
        assert clamped == _ABSOLUTE_MIN_MAX_TOKENS
