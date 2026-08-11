"""Personal ("individual," no-organization-needed) account support.

A Personal account is a normal Tenant/Organization/User under the hood
— it just never asks the person to know or type a subdomain, at signup
or at any later login. The subdomain still has to exist (every tenant
lookup goes through it), so it's derived deterministically from the
account's email instead of being client-supplied: computed identically
at signup time and at every later login, so a "subdomain-less" login
never needs a cross-tenant database query (which the app's restricted
runtime role can no longer do now that Row-Level Security is genuinely
enforced) — it just recomputes the same lookup key and reuses the
existing subdomain-based tenant resolution unchanged.
"""

from __future__ import annotations

import hashlib

_SUBDOMAIN_PREFIX = "p-"


def derive_personal_subdomain(email: str) -> str:
    """Deterministic, collision-resistant subdomain for a Personal
    account. Same email always yields the same subdomain (case- and
    whitespace-insensitive), so this can be recomputed at login time
    without storing or looking up anything extra.
    """
    normalized = email.strip().lower()
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return f"{_SUBDOMAIN_PREFIX}{digest[:20]}"


def is_personal_subdomain(subdomain: str) -> bool:
    """Whether a subdomain belongs to a Personal (not Enterprise) tenant.

    The `p-` prefix is the only signal this codebase has for this — there
    is no separate `is_personal`/`kind` column on `Tenant` — so this is
    the sole place that fact should be checked, rather than every caller
    re-matching the prefix string itself. Used by phone-login-for-
    Personal (see `personal_phone_logins` table) to decide whether a
    user's phone number should be registered for cross-tenant lookup at
    all — Enterprise phone numbers stay tenant-scoped only, since the
    same E.164 number can legitimately exist under two different
    Enterprise tenants today.
    """
    return subdomain.startswith(_SUBDOMAIN_PREFIX)
