from __future__ import annotations

import re

_SECRET_RE = re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*[a-z0-9_./+=-]{12,}")
_DATABASE_URL_RE = re.compile(r"(?i)\b(?:postgresql|postgres|mysql|sqlite)://[^\s]+")
_REDIS_URL_RE = re.compile(r"(?i)\bredis://[^\s]+")
_STACK_TRACE_RE = re.compile(r"(?i)(traceback \(most recent call last\)|file \"[^\n]+\", line \d+|sqlalchemy\.|psycopg\.|integrityerror|operationalerror)")
_PATH_RE = re.compile(r"(?i)(?:[a-z]:\\(?:users|windows|tmp|temp|program files)[^\s]*|/(?:var|tmp|home|etc|app|srv)/[^\s]+|s3://[^\s]+|gs://[^\s]+)")
_SYSTEM_PROMPT_RE = re.compile(r"(?i)\b(system prompt|developer instructions|hidden instructions|system instructions|you are chatgpt|role:\s*system|<\|system\|>)\b")
_PROMPT_RE = re.compile(r"(?i)\b(prompt[_ -]?(?:key|hash|version)|grounded_rag_answer|provider_model_name|execution_id|token_usage|estimated_cost)\b")
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I)


def detect_system_prompt_leakage(text: str) -> bool:
    return bool(_SYSTEM_PROMPT_RE.search(text))


def redact_internal_leakage(text: str, known_values: tuple[str, ...]) -> tuple[str, tuple[str, ...], bool]:
    categories: set[str] = set()
    redacted = text
    for value in sorted({item for item in known_values if item and len(item) >= 4}, key=len, reverse=True):
        if value in redacted:
            redacted = redacted.replace(value, "[redacted]")
            categories.add("known_internal_value")
    replacements = [
        (_SECRET_RE, "secret"),
        (_DATABASE_URL_RE, "database_url"),
        (_REDIS_URL_RE, "redis_url"),
        (_STACK_TRACE_RE, "stack_trace"),
        (_PATH_RE, "internal_path"),
        (_PROMPT_RE, "prompt_or_model_metadata"),
    ]
    for pattern, category in replacements:
        redacted, count = pattern.subn("[redacted]", redacted)
        if count:
            categories.add(category)
    return redacted, tuple(sorted(categories)), bool(categories)


def high_confidence_identifier_leakage(text: str, known_values: tuple[str, ...]) -> bool:
    known_hit = any(value and len(value) >= 8 and value in text for value in known_values)
    return known_hit or bool(_SECRET_RE.search(text) or _DATABASE_URL_RE.search(text) or _REDIS_URL_RE.search(text) or _STACK_TRACE_RE.search(text))


def contains_uuid_like_content(text: str) -> bool:
    return bool(_UUID_RE.search(text))