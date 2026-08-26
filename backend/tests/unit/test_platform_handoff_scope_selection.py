"""Unit tests for PlatformHandoffService._select_entitlement — the pure
logic that disambiguates which of possibly several active
career_compass_ai entitlements (Personal + one or more Enterprise orgs)
a given /platform-handoff call should honor. See that method's own
docstring and docs/adr/ADR-010-platform-identity-integration.md.
"""

from __future__ import annotations

from app.adapters.identity_providers.platform_token_verifier import PlatformEntitlement
from app.application.identity.platform_handoff import PlatformHandoffService


def _entitlement(*, org_id: str | None) -> PlatformEntitlement:
    return PlatformEntitlement(product_code="career_compass_ai", status="active", org_id=org_id)


def test_no_entitlements_returns_none() -> None:
    assert PlatformHandoffService._select_entitlement([], None) is None
    assert PlatformHandoffService._select_entitlement([], "personal") is None


def test_single_entitlement_no_scope_requested_returns_it() -> None:
    entitlement = _entitlement(org_id=None)
    assert PlatformHandoffService._select_entitlement([entitlement], None) is entitlement


def test_multi_scope_no_preference_takes_first() -> None:
    personal = _entitlement(org_id=None)
    org = _entitlement(org_id="org-1")
    assert PlatformHandoffService._select_entitlement([personal, org], None) is personal
    assert PlatformHandoffService._select_entitlement([org, personal], None) is org


def test_explicit_personal_scope_finds_direct_entitlement_regardless_of_order() -> None:
    personal = _entitlement(org_id=None)
    org = _entitlement(org_id="org-1")
    assert PlatformHandoffService._select_entitlement([org, personal], "personal") is personal


def test_explicit_org_scope_finds_matching_org_entitlement() -> None:
    personal = _entitlement(org_id=None)
    org_a = _entitlement(org_id="org-a")
    org_b = _entitlement(org_id="org-b")
    result = PlatformHandoffService._select_entitlement([personal, org_a, org_b], "org-b")
    assert result is org_b


def test_requested_scope_with_no_match_returns_none() -> None:
    personal = _entitlement(org_id=None)
    result = PlatformHandoffService._select_entitlement([personal], "org-does-not-exist")
    assert result is None
