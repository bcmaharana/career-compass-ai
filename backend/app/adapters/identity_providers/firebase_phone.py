"""Firebase Phone Auth verification adapter.

Firebase owns the entire OTP lifecycle — sending the SMS, rate-limiting/
abuse protection (reCAPTCHA), code expiry, retry counting — none of
which this backend implements or stores. The frontend talks to Firebase
directly (via the Firebase JS SDK's `signInWithPhoneNumber`/
`confirmationResult.confirm`, see frontend/src/lib/firebase.ts) and
lands here only with the resulting Firebase ID token; this adapter's one
job is to verify that token server-side and pull out the phone number
Firebase itself confirmed via SMS, so it can never be spoofed by a
client claiming an arbitrary number.

This is intentionally not a second IdentityProviderInterface
implementation — Firebase never authenticates *into* Career Compass on
its own (it has no notion of our tenants or User rows). It only proves
"this caller really controls this phone number"; matching that number to
a Career Compass user and issuing our own JWT still goes through
InternalJWTProvider.authenticate_with_phone (see internal_jwt.py),
exactly the way authenticate_with_credentials already does for
email/password.
"""

from __future__ import annotations

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from firebase_admin.exceptions import FirebaseError

from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger

logger = get_logger(__name__)


class FirebasePhoneVerifier:
    def __init__(self, *, project_id: str, service_account_file: str) -> None:
        if not project_id or not service_account_file:
            raise RuntimeError(
                "FIREBASE_PROJECT_ID and FIREBASE_SERVICE_ACCOUNT_FILE must both be set "
                "to use phone login — see backend/.env.example."
            )
        cert = credentials.Certificate(service_account_file)
        self._app = firebase_admin.initialize_app(cert, {"projectId": project_id})

    def verify_phone_number(self, id_token: str) -> str:
        """Verify a Firebase ID token and return the E.164 phone number
        Firebase confirmed for it.

        Raises UnauthorizedError if the token is missing, malformed,
        expired, revoked, or was never issued for a verified phone
        number (e.g. an email/password Firebase token, which this app
        never issues but a malicious caller could still send).
        """
        try:
            # Deliberately no check_revoked=True: that flag adds an extra
            # round-trip comparing the token's issue time against the
            # Firebase user's tokensValidAfterTime, which we've seen fail
            # intermittently (RevokedIdTokenError) for a token Firebase
            # itself had *just* issued seconds earlier — most likely
            # server-side propagation lag on Firebase's end between
            # sign-in and that timestamp settling, not a real revocation.
            # We also never call Firebase's revoke_refresh_tokens()
            # ourselves, so there's no legitimate "signed out elsewhere"
            # case this app needs to guard against — standard signature +
            # expiry verification (still real cryptographic proof of a
            # recent Firebase-confirmed phone number) is enough here.
            #
            # clock_skew_seconds=10: Docker Desktop's WSL2 VM clock can
            # drift by a second or so relative to real time (worse right
            # after the host wakes from sleep) — with zero tolerance,
            # verify_id_token intermittently rejected tokens Firebase had
            # only just issued with "Token used too early" purely because
            # the container's clock was a second behind. 10s absorbs that
            # without meaningfully loosening the expiry check itself.
            decoded = firebase_auth.verify_id_token(
                id_token, app=self._app, clock_skew_seconds=10
            )
        except (ValueError, FirebaseError) as exc:
            # ValueError: malformed token (verify_id_token validates
            # shape before ever making a Firebase call). FirebaseError:
            # everything Firebase itself rejects — expired, invalid
            # signature, wrong project, etc. (ExpiredIdTokenError/
            # InvalidIdTokenError all subclass it). Logged with the real
            # cause since the client-facing message stays generic.
            logger.warning(
                "firebase_phone_token_verification_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise UnauthorizedError(
                "Invalid or expired phone verification.", code="INVALID_PHONE_TOKEN"
            ) from exc

        phone_number = decoded.get("phone_number")
        if not phone_number:
            raise UnauthorizedError(
                "Phone verification did not include a confirmed phone number.",
                code="INVALID_PHONE_TOKEN",
            )
        return str(phone_number)
