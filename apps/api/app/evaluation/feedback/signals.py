"""Structured vocabulary for production-failure signals, mirroring the style
of app.evaluation.categories.CaseCategory - code branches on enum members,
never raw strings, so new signal types stay type-checked and discoverable in
one place.

Not every member has an automatic producer today. `AUTO_DETECTED_SIGNAL_TYPES`
is the subset app.evaluation.feedback.detector can raise on its own from
existing production data (AITrace/AIGuardrailTrace/AIModelCallTrace/
ChatMessage). The rest are accepted by the manual/API candidate-creation path
(support reports, a reviewer manually flagging a trace, a grader advisory
result, or a future thumbs-down widget feature) but have no scanner today -
see docs/03_AI/Continuous_Evaluation_Architecture.md for the full mapping and
the documented gap (no ChatMessage rating column, no widget feedback UI).
"""

from enum import Enum


class SignalType(str, Enum):
    THUMBS_DOWN = "thumbs_down"
    FALLBACK = "fallback"
    LOW_CONFIDENCE = "low_confidence"
    GROUNDING_FAILURE = "grounding_failure"
    MISSING_CITATION = "missing_citation"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    GUARDRAIL_TRIGGER = "guardrail_trigger"
    PROVIDER_FAILURE = "provider_failure"
    HIGH_LATENCY = "high_latency"
    SUPPORT_REPORT = "support_report"
    REVIEW_ITEM = "review_item"
    MANUAL_SELECTION = "manual_selection"
    GRADER_ADVISORY_FAILURE = "grader_advisory_failure"


SIGNAL_TYPE_VALUES = frozenset(member.value for member in SignalType)

AUTO_DETECTED_SIGNAL_TYPES = frozenset(
    {
        SignalType.FALLBACK,
        SignalType.LOW_CONFIDENCE,
        SignalType.MISSING_CITATION,
        SignalType.GUARDRAIL_TRIGGER,
        SignalType.PROVIDER_FAILURE,
        SignalType.HIGH_LATENCY,
    }
)

# Signal types severe enough on a single occurrence to create a candidate
# immediately; everything else only creates a candidate once it has recurred
# (see detector.py's dedup-first creation bar - "do not treat every fallback
# as a defect").
SEVERE_ON_FIRST_OCCURRENCE = frozenset(
    {
        SignalType.GUARDRAIL_TRIGGER,
        SignalType.PROVIDER_FAILURE,
    }
)

TRIAGE_STATUSES = frozenset({"new", "triaged", "needs_information", "accepted", "rejected", "duplicate", "resolved"})
TERMINAL_TRIAGE_STATUSES = frozenset({"rejected", "duplicate", "resolved"})
SEVERITY_LEVELS = frozenset({"low", "medium", "high", "critical"})
