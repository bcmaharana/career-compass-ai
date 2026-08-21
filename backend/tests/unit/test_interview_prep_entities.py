"""Unit tests for app/domain/interview_prep/entities.py's
is_safe_reference_url — a pure function, tested directly rather than
only indirectly through the service-level rejection tests in
test_interview_question_service.py / test_interview_topic_service.py.
"""

from __future__ import annotations

import pytest

from app.domain.interview_prep.entities import is_safe_reference_url

pytestmark = pytest.mark.unit


class TestIsSafeReferenceUrl:
    def test_https_is_safe(self) -> None:
        assert is_safe_reference_url("https://example.com/article") is True

    def test_http_is_safe(self) -> None:
        assert is_safe_reference_url("http://example.com") is True

    def test_mailto_is_safe(self) -> None:
        assert is_safe_reference_url("mailto:someone@example.com") is True

    def test_scheme_less_host_is_safe(self) -> None:
        # Matches this app's own deliberately-permissive LinkedIn/
        # credential-URL precedent — a bare host/path has no scheme for
        # a browser to execute.
        assert is_safe_reference_url("linkedin.com/in/someone") is True

    def test_uppercase_scheme_is_still_recognized(self) -> None:
        assert is_safe_reference_url("HTTPS://example.com") is True

    def test_javascript_scheme_is_unsafe(self) -> None:
        assert is_safe_reference_url("javascript:alert(document.cookie)") is False

    def test_javascript_scheme_with_leading_whitespace_is_unsafe(self) -> None:
        # A naive check for "://" would have let this straight through —
        # javascript: URIs never use "//" after the colon.
        assert is_safe_reference_url("  javascript:alert(1)") is False

    def test_data_scheme_is_unsafe(self) -> None:
        assert is_safe_reference_url("data:text/html,<script>alert(1)</script>") is False

    def test_vbscript_scheme_is_unsafe(self) -> None:
        assert is_safe_reference_url("vbscript:msgbox(1)") is False

    def test_file_scheme_is_unsafe(self) -> None:
        assert is_safe_reference_url("file:///etc/passwd") is False
