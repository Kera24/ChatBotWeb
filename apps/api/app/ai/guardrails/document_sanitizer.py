"""Layer E: indirect prompt-injection defence.

Retrieved document content is untrusted data (see the trust-boundary framing
added to the `grounded_rag_answer` prompt in app.ai.prompt_registry). This
module is the deterministic, structural half of that defence: it strips
injected-instruction-style text out of retrieved chunk content *before* it is
assembled into context, so the generation model never even sees the
attempted override - a defense-in-depth layer independent of (and in
addition to) whatever the prompt framing achieves with a real generation
model, which this evaluation cycle's deterministic mock provider cannot
validate end to end (see docs/04_Engineering/Guardrails_Task_Specification.md's
constraint note).

Deliberately removes only the matched injected-instruction span, preserving
the surrounding legitimate factual content of the document - the assistant
should still be able to cite and use the rest of a document that happens to
contain a poisoned sentence, per the task's explicit requirement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Reuses the same trigger-phrase families as app.ai.guardrails.input_policy's
# direct-injection patterns, since a document-embedded attack and a
# user-message attack use the same language - only the source differs. Also
# matches common "fake system message" formatting (bracketed or ALL-CAPS
# "SYSTEM:"-style headers) and a couple of encoded/obfuscated variants.
_INJECTED_INSTRUCTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?is)\[\s*SYSTEM[^\]]{0,300}\]"),
    re.compile(r"(?im)^\s*SYSTEM\s*(OVERRIDE|MESSAGE|:)\s*.{0,300}$"),
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions?[^.\n]{0,200}[.\n]"),
    re.compile(r"(?i)reveal\s+(the\s+|your\s+)?(system\s+prompt|admin\s+password|database\s+connection\s+string|internal\s+api\s+keys?)[^.\n]{0,200}[.\n]?"),
    re.compile(r"(?i)you\s+are\s+no\s+longer\s+a\s+.{0,60}assistant[^.\n]{0,200}[.\n]?"),
    re.compile(r"(?i)do\s+not\s+cite\s+this\s+document[^.\n]{0,200}[.\n]?"),
    re.compile(r"(?i)disregard\s+(the\s+)?(knowledge\s*base|system\s+policy)[^.\n]{0,200}[.\n]?"),
)

_REDACTION_MARKER = "[content removed: embedded instruction pattern]"


@dataclass(frozen=True)
class SanitisedEvidence:
    content: str
    was_modified: bool
    matched_pattern_count: int


def sanitise_evidence_content(content: str) -> SanitisedEvidence:
    matched = 0
    result = content
    for pattern in _INJECTED_INSTRUCTION_PATTERNS:
        result, count = pattern.subn(_REDACTION_MARKER, result)
        matched += count
    return SanitisedEvidence(content=result, was_modified=matched > 0, matched_pattern_count=matched)
