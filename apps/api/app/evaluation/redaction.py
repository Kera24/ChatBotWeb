"""Strip anything that looks like a secret or connection string out of text
before it is persisted on an EvaluationResult or shown in a report.

Evaluation results are inspected by developers and administrators, but the
underlying error text (exceptions, provider messages) can accidentally carry
whatever the failing call had in scope. Treat every error message as
untrusted output and redact defensively rather than relying on callers to be
careful every time.
"""

import re

_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(postgres(?:ql)?|mysql|redis|mongodb)://[^\s\"']+"),
    re.compile(r"(?i)(sk-[a-z0-9]{16,})"),
    re.compile(r"(?i)(whsec_[a-z0-9]{16,})"),
    re.compile(r"(?i)((?:api[_-]?key|secret|password|token)\s*[:=]\s*)([^\s\"']{4,})"),
)

_REPLACEMENT = "[REDACTED]"


def redact_secrets(text: str | None) -> str | None:
    if not text:
        return text
    redacted = text
    for pattern in _PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(lambda match: f"{match.group(1)}{_REPLACEMENT}", redacted)
        else:
            redacted = pattern.sub(_REPLACEMENT, redacted)
    return redacted


def safe_error_message(exc: BaseException, *, max_length: int = 500) -> str:
    """A short, redacted, tenant-safe description of an exception for storage."""
    message = redact_secrets(str(exc)) or exc.__class__.__name__
    if len(message) > max_length:
        message = f"{message[:max_length]}..."
    return message
