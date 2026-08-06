"""Layers G (system-prompt/secret protection) and H (output sanitisation): a
deterministic, post-generation check and transform applied to whatever text
the AI provider returned, before it is persisted or returned to a caller.

Applied identically regardless of caller (authenticated dashboard chat,
public widget, evaluation runner - see app.ai.rag_orchestrator.RAGOrchestrator,
the single shared code path all three use), so there is exactly one place
this enforcement lives, not three separate implementations.

Detection patterns here intentionally extend (not replace) the read-only
detection patterns already used for evaluation *scoring* in
app.evaluation.metrics.answer - this module additionally *acts* on what it
finds (neutralises markup, replaces leaked content with a safe refusal)
rather than only measuring it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.guardrails.reason_codes import GuardrailReasonCode

SAFE_REFUSAL_SECRET = "I can't share credentials, API keys, or connection details."
SAFE_REFUSAL_PROMPT_LEAKAGE = "I can't share internal system instructions or configuration details."

# --- secret / prompt-leakage detection (never persist the matched value itself) ---

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(postgres(?:ql)?|mysql|redis|mongodb)://\S+"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bwhsec_[A-Za-z0-9]{16,}\b"),
    re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|password|passwd)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{20,}\b"),
)

_PROMPT_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bmy (system )?instructions (are|say)\b"),
    re.compile(r"(?i)\bsystem prompt\b"),
    re.compile(r"(?i)\byou are (a|an) [a-z ]{0,40}(assistant|model|ai)\b.{0,40}(grounded|must|should|only)"),
    re.compile(r"(?i)\bignore (all )?(previous|prior|above) instructions\b"),
    re.compile(r"(?i)\bprompt (key|version|template)\s*[:=]"),
    re.compile(r"(?i)\binternal configuration\b"),
)

# --- unsafe markup: neutralised (removed/de-fanged), not merely flagged ---

_SCRIPT_BLOCK = re.compile(r"(?is)<script\b[^>]*>.*?</script\s*>")
_DANGEROUS_TAGS = re.compile(r"(?is)<(iframe|object|embed)\b[^>]*>.*?</\1\s*>|<(iframe|object|embed)\b[^>]*/?>")
_EVENT_HANDLER_ATTR = re.compile(r"(?i)\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")
_JAVASCRIPT_URI = re.compile(r"(?i)javascript:")


@dataclass(frozen=True)
class OutputSafetyVerdict:
    safe: bool
    reason_code: GuardrailReasonCode
    sanitised_text: str
    safe_message: str | None = None


def sanitise_markup(text: str) -> str:
    """Neutralises dangerous markup while leaving normal Markdown (bold,
    links to safe schemes, lists, headings) untouched."""
    result = _SCRIPT_BLOCK.sub("", text)
    result = _DANGEROUS_TAGS.sub("", result)
    result = _EVENT_HANDLER_ATTR.sub("", result)
    result = _JAVASCRIPT_URI.sub("blocked:", result)
    return result


def check_output_safety(text: str) -> OutputSafetyVerdict:
    """Runs sanitisation first (so a markup-only issue is silently fixed and
    still returns `safe=True` with the cleaned text), then checks for secret
    or prompt-leakage patterns, which are not merely stripped - the caller
    receives a safe refusal message and `safe=False` instead of any partial
    leaked content, since redacting only the matched span could still leave
    enough surrounding context to be useful to an attacker."""
    sanitised = sanitise_markup(text)

    for pattern in _SECRET_PATTERNS:
        if pattern.search(sanitised):
            return OutputSafetyVerdict(safe=False, reason_code=GuardrailReasonCode.BLOCKED_SECRET_PATTERN, sanitised_text=SAFE_REFUSAL_SECRET, safe_message=SAFE_REFUSAL_SECRET)

    for pattern in _PROMPT_LEAK_PATTERNS:
        if pattern.search(sanitised):
            return OutputSafetyVerdict(safe=False, reason_code=GuardrailReasonCode.BLOCKED_PROMPT_LEAKAGE, sanitised_text=SAFE_REFUSAL_PROMPT_LEAKAGE, safe_message=SAFE_REFUSAL_PROMPT_LEAKAGE)

    return OutputSafetyVerdict(safe=True, reason_code=GuardrailReasonCode.OUTPUT_SAFE, sanitised_text=sanitised)
