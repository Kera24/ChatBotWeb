"""Central, closed vocabulary of guardrail reason codes.

Every guardrail layer returns one of these instead of a free-text string, so
downstream code (observability, evaluation scoring, the review queue) can
branch on a known, typed value rather than string-matching. See
docs/04_Engineering/Guardrails_Task_Specification.md for the failure-category
definitions these map to.

`answer_state` on a persisted message stays within the existing, small,
UI-known vocabulary (`answered`/`fallback`/`failed`/`low_confidence`/`pending`
- see app.services.conversation.VALID_ANSWER_STATES) so no dashboard/widget
rendering code needs to change; the specific *reason* a guardrail intervened
is recorded separately in message/result metadata as one of these codes. This
keeps API/schema compatibility exactly as it was before this task.
"""

from enum import Enum


class GuardrailReasonCode(str, Enum):
    # Grounding (Layer A/B)
    GROUNDING_PASSED = "grounding_passed"
    NO_AUTHORISED_EVIDENCE = "no_authorised_evidence"
    NO_VALID_CITATIONS = "no_valid_citations"
    REQUESTED_FACT_NOT_SUPPORTED = "requested_fact_not_supported"
    UNSUPPORTED_CITATION = "unsupported_citation"
    EVIDENCE_BELOW_THRESHOLD = "evidence_below_threshold"
    MALFORMED_ANSWER = "malformed_answer"

    # Evidence sufficiency verifier (app.ai.guardrails.evidence_sufficiency) -
    # supersedes the simpler grounding.py term-presence check for cases where
    # a requested-attribute/value-type/proximity signal is available. Kept as
    # a distinct code set (not a rename of the grounding codes above) so
    # existing grounding.py callers/tests are unaffected.
    SUFFICIENT_EVIDENCE = "sufficient_evidence"
    REQUESTED_FACT_ABSENT = "requested_fact_absent"
    RELATED_TOPIC_ONLY = "related_topic_only"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    AMBIGUOUS_REQUEST = "ambiguous_request"

    # Capability / intent (Layer C)
    ALLOWED_KNOWLEDGE_QUESTION = "allowed_knowledge_question"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    PROHIBITED_INTERNAL_REQUEST = "prohibited_internal_request"
    CROSS_SCOPE_REQUEST = "cross_scope_request"
    MALFORMED_REQUEST = "malformed_request"

    # Direct / indirect prompt injection (Layer D/E)
    DIRECT_PROMPT_INJECTION_BLOCKED = "direct_prompt_injection_blocked"
    INDIRECT_PROMPT_INJECTION_NEUTRALISED = "indirect_prompt_injection_neutralised"

    # System-prompt / secret protection (Layer G)
    BLOCKED_SECRET_PATTERN = "blocked_secret_pattern"
    BLOCKED_PROMPT_LEAKAGE = "blocked_prompt_leakage"
    BLOCKED_INTERNAL_CONFIGURATION = "blocked_internal_configuration"
    OUTPUT_SAFE = "output_safe"

    # Output sanitisation (Layer H)
    UNSAFE_MARKUP_SANITISED = "unsafe_markup_sanitised"

    # Citation enforcement (Layer F)
    CITATION_INVALID = "citation_invalid"
    CITATION_FOREIGN_SCOPE = "citation_foreign_scope"

    # Provider-level (existing behaviour, given a name in this vocabulary too)
    PROVIDER_FAILED = "provider_failed"
    PROVIDER_TIMEOUT = "provider_timeout"
    MALFORMED_PROVIDER_OUTPUT = "malformed_provider_output"

    # Retrieval (existing, pre-dates this task)
    RETRIEVAL_EMPTY = "retrieval_empty"


REASON_CODE_VALUES = frozenset(member.value for member in GuardrailReasonCode)
