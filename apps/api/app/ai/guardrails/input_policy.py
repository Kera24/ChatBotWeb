"""Layers C (capability/intent boundaries) and D (direct prompt-injection
defence): a deterministic, pre-generation check on the user's own question.

Deliberately runs BEFORE retrieval and BEFORE any AI provider call - a
blocked request never reaches generation at all, so this layer is fully
enforced and testable regardless of which AI provider (mock or real) is
configured; it does not depend on how a model would have responded.

Every pattern here requires the co-occurrence of a trigger phrase AND a
specific target noun (e.g. "ignore" + "instructions", not "ignore" alone) so
that ordinary business language using words like "system," "prompt,"
"ignore," "override," or "disregard" in a benign sense is not blocked - see
the benign_edge_case golden dataset cases this is tested against.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.guardrails.reason_codes import GuardrailReasonCode

SAFE_REFUSAL_PROMPT_LEAKAGE = "I can't share internal system instructions or configuration details. I'm happy to answer questions using the knowledge base instead."
SAFE_REFUSAL_INJECTION = "I can't follow instructions that ask me to change how I operate. I'm happy to help with a question about the knowledge base."
SAFE_REFUSAL_SECRET = "I can't share credentials, API keys, or connection details. I'm happy to help with a question about the knowledge base."
SAFE_REFUSAL_CAPABILITY = "I'm not able to take that action - I can only answer questions using the approved knowledge base. Please contact support directly for account, billing, or security requests."


@dataclass(frozen=True)
class InputPolicyVerdict:
    allowed: bool
    reason_code: GuardrailReasonCode
    safe_message: str | None = None


# Each pattern requires an explicit target noun alongside the trigger verb,
# not the verb alone, to avoid blocking ordinary sentences.
_PROMPT_EXTRACTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bsystem['’]?s?\s+prompt\b"),
    re.compile(r"(?i)\breveal\b.{0,30}\b(system|internal|your)\b.{0,20}\b(instructions?|prompt|configuration)\b"),
    re.compile(r"(?i)\brepeat\b.{0,40}\binstructions?\b"),
    re.compile(r"(?i)\bwhat\s+(model|provider)\b.{0,30}\brunning\b"),
    re.compile(r"(?i)\bprompt\s+template\b"),
    re.compile(r"(?i)\bconfiguration\s+variables?\b"),
    re.compile(r"(?i)\binternal\s+configuration\b"),
    re.compile(r"(?i)\byour\s+instructions?\s+(were|are|verbatim)\b"),
)

_DIRECT_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bignore\b.{0,20}\b(all\s+)?(previous|prior|above)\s+instructions?\b"),
    re.compile(r"(?i)\bdisregard\b.{0,20}\b(the\s+)?(knowledge\s*base|instructions?)\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+in\b.{0,20}\bmode\b"),
    re.compile(r"(?i)\bact\s+as\s+(an?\s+)?unrestricted\b"),
    re.compile(r"(?i)\bpretend\s+you\s+are\b.{0,30}\b(unrestricted|no\s+(policies|restrictions|rules))\b"),
    re.compile(r"(?i)\bnew\s+instructions?\s+follow\b"),
    re.compile(r"(?i)\btreat\s+the\s+following\b.{0,20}\bas\s+system\b"),
    re.compile(r"(?i)\bbypass\s+citations?\b"),
    re.compile(r"(?i)\bno\s+(restrictions|policies)\b.{0,20}\bfrom\s+now\s+on\b"),
    re.compile(r"(?i)\bdeveloper\s+mode\b"),
    re.compile(r"(?i)\bpretend\s+the\s+knowledge\s*base\s+contains\b"),
    re.compile(r"(?i)\banother\s+assistant['’]?s\s+documents?\b"),
)

_SECRET_EXTRACTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(database|billing|admin)\s+connection\s+string\b"),
    re.compile(r"(?i)\binternal\s+api\s+keys?\b"),
    re.compile(r"(?i)\badmin\s+password\b"),
    re.compile(r"(?i)\bwebhook\s+secret\b"),
    re.compile(r"(?i)\bsession\s+tokens?\b.{0,20}\b(reveal|show|print|output)\b"),
    re.compile(r"(?i)\b(output|print|show)\b.{0,20}\bcredentials?\b"),
)

# Transactional/imperative action requests: a sensitive verb + a sensitive
# object + urgency/imperative framing. Deliberately does NOT match a plain
# informational question about a process ("what is the process for X",
# "how do I request X") - only an imperative demand that the assistant
# perform the action itself, right now, on the user's behalf.
_CAPABILITY_VIOLATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(can\s+you|please|could\s+you)\b.{0,20}\b(process|issue)\b.{0,20}\brefund\b"),
    re.compile(r"(?i)\b(can\s+you|please|could\s+you)\b.{0,20}\bchange\s+my\s+subscription\b"),
    re.compile(r"(?i)\b(please\s+)?permanently\s+delete\s+(my|this|the)\b.{0,20}\b(workspace|account|data)\b"),
    re.compile(r"(?i)\bcancel\s+my\s+(subscription|account|plan)\b.{0,20}\b(now|immediately|right\s+now)\b"),
    re.compile(r"(?i)\b(hacked|breach(ed)?|compromised)\b.{0,60}\b(what\s+do\s+i\s+do|help\s+me|right\s+now)\b"),
)

_CROSS_SCOPE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bother\s+assistant\b.{0,30}\bknow(s)?\b"),
    re.compile(r"(?i)\bother\s+(workspace|organisation|organization)\b.{0,40}\b(say|policy|data|rate\s+limits?)\b"),
    re.compile(r"(?i)\bdifferent\s+(customer\s+)?organisation\b"),
    re.compile(r"(?i)\bunrelated\s+customer\b"),
)


def evaluate_input_policy(query: str) -> InputPolicyVerdict:
    if _matches_any(query, _SECRET_EXTRACTION_PATTERNS):
        return InputPolicyVerdict(allowed=False, reason_code=GuardrailReasonCode.PROHIBITED_INTERNAL_REQUEST, safe_message=SAFE_REFUSAL_SECRET)
    if _matches_any(query, _PROMPT_EXTRACTION_PATTERNS):
        return InputPolicyVerdict(allowed=False, reason_code=GuardrailReasonCode.PROHIBITED_INTERNAL_REQUEST, safe_message=SAFE_REFUSAL_PROMPT_LEAKAGE)
    if _matches_any(query, _DIRECT_INJECTION_PATTERNS):
        return InputPolicyVerdict(allowed=False, reason_code=GuardrailReasonCode.DIRECT_PROMPT_INJECTION_BLOCKED, safe_message=SAFE_REFUSAL_INJECTION)
    if _matches_any(query, _CAPABILITY_VIOLATION_PATTERNS):
        return InputPolicyVerdict(allowed=False, reason_code=GuardrailReasonCode.UNSUPPORTED_CAPABILITY, safe_message=SAFE_REFUSAL_CAPABILITY)
    if _matches_any(query, _CROSS_SCOPE_PATTERNS):
        return InputPolicyVerdict(allowed=False, reason_code=GuardrailReasonCode.CROSS_SCOPE_REQUEST, safe_message=SAFE_REFUSAL_CAPABILITY)
    return InputPolicyVerdict(allowed=True, reason_code=GuardrailReasonCode.ALLOWED_KNOWLEDGE_QUESTION)


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)
