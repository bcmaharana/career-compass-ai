"""Resend-backed email provider (password reset).

No official async SDK dependency is added for this — a plain httpx POST
against Resend's REST API, same pattern as ZenQuotesProvider/
OllamaProvider for providers without a heavy existing SDK already in the
project. Lazy about missing configuration, matching AnthropicProvider:
constructs fine with no API key, only raises when send_email() is
actually called.
"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.core.email_provider_interface import EmailMessage
from app.core.exceptions import CareerCompassError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ResendProviderError(CareerCompassError):
    code = "EMAIL_PROVIDER_ERROR"


class ResendEmailProvider:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.resend_api_key or None
        self._from_email = settings.resend_from_email

    async def send_email(self, message: EmailMessage) -> None:
        if self._api_key is None:
            raise ResendProviderError(
                "Resend API key is not configured (RESEND_API_KEY).",
                code="EMAIL_PROVIDER_NOT_CONFIGURED",
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "from": self._from_email,
                        "to": [message.to],
                        "subject": message.subject,
                        "html": message.html_body,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            # The raw exception (for an HTTPStatusError, this includes
            # Resend's own response body) is logged server-side only —
            # it can contain vendor-internal wording (e.g. sandbox
            # restrictions on the recipient domain) that shouldn't be
            # relayed verbatim to whoever triggered the send (this
            # provider's callers include self-serve signup, which
            # deliberately surfaces send failures rather than swallowing
            # them — see RequestPersonalSignupService's docstring).
            logger.warning("resend_send_failed", error=str(exc))
            raise ResendProviderError("Failed to send the email. Please try again shortly.") from exc
