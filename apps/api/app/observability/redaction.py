from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from app.core.config import settings
from app.operations.logging import _PUBLIC_KEY_PATTERN, _SESSION_TOKEN_PATTERN, pseudonymous_identifier

logger = logging.getLogger("chatbotweb.observability.redaction")

# Free-text pattern-based redaction for RAG prompt/response *content* - a
# different risk surface than app.operations.logging.redact()'s
# key-name-based structured-log redaction (customer-typed PII, or a secret a
# user pasted into a chat message, rather than an internal field we know by
# name). Structural secrets are matched before generic PII so a token
# embedded inside an email-shaped string isn't half-redacted by the weaker
# pattern first.
_STRIPE_SECRET_PATTERN = re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{10,}\b")
_STRIPE_WEBHOOK_PATTERN = re.compile(r"\bwhsec_[A-Za-z0-9]{10,}\b")
_AWS_ACCESS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_BEARER_TOKEN_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._-]{16,}\b", re.IGNORECASE)
_DB_CONNECTION_PATTERN = re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://\S+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d[\d\-.\s()]{7,}\d)(?!\d)")

_STRUCTURAL_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("stripe_secret_key", _STRIPE_SECRET_PATTERN),
    ("stripe_webhook_secret", _STRIPE_WEBHOOK_PATTERN),
    ("aws_access_key", _AWS_ACCESS_KEY_PATTERN),
    ("jwt", _JWT_PATTERN),
    ("bearer_token", _BEARER_TOKEN_PATTERN),
    ("db_connection_string", _DB_CONNECTION_PATTERN),
    ("public_widget_key", _PUBLIC_KEY_PATTERN),
    ("session_token", _SESSION_TOKEN_PATTERN),
)
_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", _EMAIL_PATTERN),
    ("phone", _PHONE_PATTERN),
)

# Bumped whenever the pattern set above changes in a way that would affect
# already-redacted content (e.g. a new structural-secret pattern added). Rows
# that persist a redacted preview (AITrace content, EvaluationCandidate
# question/response) store this alongside the text so a later audit can tell
# which ruleset produced it.
REDACTION_RULESET_VERSION = "v1"

CONTENT_MODE_METADATA_ONLY = "metadata_only"
CONTENT_MODE_REDACTED_PREVIEW = "redacted_preview"
CONTENT_MODE_ENCRYPTED_FULL_CONTENT = "encrypted_full_content"
VALID_CONTENT_MODES = (CONTENT_MODE_METADATA_ONLY, CONTENT_MODE_REDACTED_PREVIEW, CONTENT_MODE_ENCRYPTED_FULL_CONTENT)

_warned_encrypted_mode_unimplemented = False


@dataclass(frozen=True)
class RedactionResult:
    text: str
    categories_triggered: tuple[str, ...]

    @property
    def had_redactions(self) -> bool:
        return bool(self.categories_triggered)


def load_custom_redaction_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Parses AI_TRACE_CUSTOM_REDACTION_PATTERNS - a JSON array of
    {"name": ..., "pattern": ...} objects - into compiled patterns. Invalid
    configuration is logged and ignored rather than crashing the process,
    matching this module's fail-safe posture."""
    raw = settings.AI_TRACE_CUSTOM_REDACTION_PATTERNS.strip()
    if not raw:
        return ()
    try:
        entries = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("AI_TRACE_CUSTOM_REDACTION_PATTERNS is not valid JSON; ignoring.")
        return ()
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for entry in entries if isinstance(entries, list) else []:
        try:
            name = str(entry["name"])
            pattern = re.compile(str(entry["pattern"]))
        except (KeyError, re.error, TypeError):
            logger.warning("Skipping invalid entry in AI_TRACE_CUSTOM_REDACTION_PATTERNS: %r", entry)
            continue
        patterns.append((name, pattern))
    return tuple(patterns)


def redact_free_text(value: str, *, custom_patterns: tuple[tuple[str, re.Pattern[str]], ...] | None = None) -> RedactionResult:
    if not value:
        return RedactionResult(text=value, categories_triggered=())

    text = value
    triggered: list[str] = []
    for name, pattern in _STRUCTURAL_SECRET_PATTERNS:
        if pattern.search(text):
            triggered.append(name)
            if name == "public_widget_key":
                text = pattern.sub(lambda match: pseudonymous_identifier(match.group(0), prefix="widget"), text)
            else:
                text = pattern.sub(f"[redacted-{name}]", text)

    for name, pattern in custom_patterns if custom_patterns is not None else load_custom_redaction_patterns():
        if pattern.search(text):
            triggered.append(name)
            text = pattern.sub(f"[redacted-{name}]", text)

    for name, pattern in _PII_PATTERNS:
        if pattern.search(text):
            triggered.append(name)
            text = pattern.sub(f"[redacted-{name}]", text)

    return RedactionResult(text=text, categories_triggered=tuple(triggered))


def apply_retention_policy(raw_text: str | None, *, mode: str, max_preview_chars: int = 500) -> str | None:
    """Applies the configured AI trace content-retention policy to one blob
    of prompt/response/chunk text before it is ever written to an
    AIRetrievalTrace/AIModelCallTrace row. `metadata_only` (the default)
    stores nothing at all."""
    if raw_text is None:
        return None
    if mode == CONTENT_MODE_METADATA_ONLY:
        return None
    if mode == CONTENT_MODE_ENCRYPTED_FULL_CONTENT:
        _warn_encrypted_mode_unimplemented_once()
        mode = CONTENT_MODE_REDACTED_PREVIEW
    if mode != CONTENT_MODE_REDACTED_PREVIEW:
        # Unknown/misconfigured mode - fail closed to the safest option
        # rather than accidentally persisting raw content.
        return None

    redacted = redact_free_text(raw_text).text
    if len(redacted) <= max_preview_chars:
        return redacted
    return redacted[:max_preview_chars] + "…[truncated]"


def _warn_encrypted_mode_unimplemented_once() -> None:
    global _warned_encrypted_mode_unimplemented
    if _warned_encrypted_mode_unimplemented:
        return
    _warned_encrypted_mode_unimplemented = True
    logger.warning(
        "AI_TRACE_CONTENT_MODE=encrypted_full_content is not implemented yet (requires a KMS/key-management "
        "decision); falling back to redacted_preview behaviour for all AI trace content."
    )
