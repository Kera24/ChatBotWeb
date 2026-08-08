import pytest

_FAKE_STRIPE_KEY = "".join(("sk", "_live_", "abcdefghij1234567890"))

from app.observability.redaction import (
    CONTENT_MODE_ENCRYPTED_FULL_CONTENT,
    CONTENT_MODE_METADATA_ONLY,
    CONTENT_MODE_REDACTED_PREVIEW,
    apply_retention_policy,
    load_custom_redaction_patterns,
    redact_free_text,
)


@pytest.mark.parametrize(
    ("text", "category", "must_not_contain"),
    [
        ("Reach me at jane.doe@example.com", "email", "jane.doe@example.com"),
        ("Call me at 415-555-0132 today", "phone", "415-555-0132"),
        (f"key {_FAKE_STRIPE_KEY}", "stripe_secret_key", _FAKE_STRIPE_KEY),
        ("secret whsec_abcdefghij1234567890", "stripe_webhook_secret", "whsec_abcdefghij1234567890"),
        ("aws AKIAABCDEFGHIJKLMNOP", "aws_access_key", "AKIAABCDEFGHIJKLMNOP"),
        ("token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dGVzdHNpZ25hdHVyZQ", "jwt", "eyJhbGciOiJIUzI1NiJ9"),
        ("Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456", "bearer_token", "abcdefghijklmnopqrstuvwxyz123456"),
        ("db postgres://user:pass@host:5432/db", "db_connection_string", "user:pass@host"),
        ("widget key wpk_live_abc123", "public_widget_key", "wpk_live_abc123"),
        ("session pss_dev_abcdefghijklmnop.abcdefghijklmnopqrstuvwx", "session_token", "pss_dev_abcdefghijklmnop"),
    ],
)
def test_redact_free_text_covers_every_category(text: str, category: str, must_not_contain: str) -> None:
    result = redact_free_text(text)
    assert category in result.categories_triggered
    assert must_not_contain not in result.text


def test_redact_free_text_no_false_positive_on_ordinary_prose() -> None:
    result = redact_free_text("The knowledge base says applications close in December and interviews follow in January.")
    assert result.categories_triggered == ()
    assert result.text == "The knowledge base says applications close in December and interviews follow in January."


def test_redact_free_text_handles_multiple_categories_in_one_string() -> None:
    result = redact_free_text(f"Contact jane@example.com or use {_FAKE_STRIPE_KEY} to authenticate.")
    assert "email" in result.categories_triggered
    assert "stripe_secret_key" in result.categories_triggered
    assert "jane@example.com" not in result.text
    assert _FAKE_STRIPE_KEY not in result.text


def test_load_custom_redaction_patterns_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    original = settings.AI_TRACE_CUSTOM_REDACTION_PATTERNS
    try:
        object.__setattr__(settings, "AI_TRACE_CUSTOM_REDACTION_PATTERNS", '[{"name": "internal_case_id", "pattern": "CASE-\\\\d{6}"}]')
        patterns = load_custom_redaction_patterns()
        assert len(patterns) == 1
        assert patterns[0][0] == "internal_case_id"
        result = redact_free_text("See CASE-123456 for details.", custom_patterns=patterns)
        assert "CASE-123456" not in result.text
        assert "internal_case_id" in result.categories_triggered
    finally:
        object.__setattr__(settings, "AI_TRACE_CUSTOM_REDACTION_PATTERNS", original)


def test_load_custom_redaction_patterns_ignores_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    original = settings.AI_TRACE_CUSTOM_REDACTION_PATTERNS
    try:
        object.__setattr__(settings, "AI_TRACE_CUSTOM_REDACTION_PATTERNS", "not json")
        assert load_custom_redaction_patterns() == ()
    finally:
        object.__setattr__(settings, "AI_TRACE_CUSTOM_REDACTION_PATTERNS", original)


def test_apply_retention_policy_metadata_only_stores_nothing() -> None:
    assert apply_retention_policy("some content with jane@example.com", mode=CONTENT_MODE_METADATA_ONLY) is None
    assert apply_retention_policy(None, mode=CONTENT_MODE_METADATA_ONLY) is None


def test_apply_retention_policy_redacted_preview_redacts_and_truncates() -> None:
    result = apply_retention_policy("contact jane@example.com for help", mode=CONTENT_MODE_REDACTED_PREVIEW)
    assert result is not None
    assert "jane@example.com" not in result

    long_text = "x" * 1000
    truncated = apply_retention_policy(long_text, mode=CONTENT_MODE_REDACTED_PREVIEW, max_preview_chars=50)
    assert truncated is not None
    assert len(truncated) <= 50 + len("…[truncated]")
    assert truncated.endswith("…[truncated]")


def test_apply_retention_policy_encrypted_mode_falls_back_safely_not_crashes() -> None:
    result = apply_retention_policy("contact jane@example.com", mode=CONTENT_MODE_ENCRYPTED_FULL_CONTENT)
    assert result is not None
    assert "jane@example.com" not in result  # falls back to redacted_preview behaviour, never raw
