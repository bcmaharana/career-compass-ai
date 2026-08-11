"""Unit tests for derive_personal_subdomain."""

from __future__ import annotations

import re

import pytest

from app.domain.identity.personal_accounts import derive_personal_subdomain

_SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9-]+$")


@pytest.mark.unit
class TestDerivePersonalSubdomain:
    def test_same_email_yields_the_same_subdomain(self) -> None:
        first = derive_personal_subdomain("jordan@example.com")
        second = derive_personal_subdomain("jordan@example.com")
        assert first == second

    def test_different_emails_yield_different_subdomains(self) -> None:
        assert derive_personal_subdomain("jordan@example.com") != derive_personal_subdomain(
            "rivera@example.com"
        )

    def test_case_insensitive(self) -> None:
        assert derive_personal_subdomain("Jordan@Example.com") == derive_personal_subdomain(
            "jordan@example.com"
        )

    def test_whitespace_insensitive(self) -> None:
        assert derive_personal_subdomain("  jordan@example.com  ") == derive_personal_subdomain(
            "jordan@example.com"
        )

    def test_output_matches_subdomain_constraints(self) -> None:
        subdomain = derive_personal_subdomain("jordan@example.com")
        assert 1 <= len(subdomain) <= 63
        assert _SUBDOMAIN_PATTERN.match(subdomain)
