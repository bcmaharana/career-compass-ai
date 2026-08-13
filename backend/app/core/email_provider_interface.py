"""Email-sending provider abstraction (password reset).

Application services depend only on `EmailProviderInterface`, not on any
specific vendor's SDK/API shape — swapping providers means writing a new
adapter against this interface, not touching callers, the same shape as
`QuoteProviderInterface` in this module's sibling file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    html_body: str
    # None = use the provider's configured default sender (settings.resend_from_email).
    # Set to send from a different verified address on the same domain
    # (e.g. welcome@scaledbrain.com for the welcome email) without a
    # second provider instance.
    from_email: str | None = None


class EmailProviderInterface(Protocol):
    async def send_email(self, message: EmailMessage) -> None:
        """Send an email.

        Raises app.adapters.email.resend_provider.ResendProviderError (or
        any other CareerCompassError) on failure — callers in the
        password-reset flow deliberately catch and log this rather than
        letting it propagate, since a provider outage must not turn into
        a response that reveals whether a given account exists.
        """
        ...
