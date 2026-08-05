"""Structured vocabulary for evaluation cases.

Code must branch on these enum members rather than matching raw strings so new
case types stay type-checked and discoverable in one place.

Some requested case "types" from the evaluation task specification are
intentionally modeled as tags rather than new categories, since they are
input-shape/phrasing variants of an existing category rather than a distinct
behavioural expectation: paraphrased variants and specific-source-document
questions are tagged onto ANSWERABLE_FACTUAL/CITATION_REQUIRED cases (tags
"paraphrase" / "specific-source"); clarification-needed questions are tagged
onto AMBIGUOUS cases (tag "clarification-needed") - see
docs/04_Engineering/Evaluation_Task_Specification.md for the full mapping and
the documented capability gap (no clarification answer_state exists today).
"""

from enum import Enum


class CaseCategory(str, Enum):
    ANSWERABLE_FACTUAL = "answerable_factual"
    UNANSWERABLE = "unanswerable"
    CITATION_REQUIRED = "citation_required"
    MULTI_DOCUMENT = "multi_document"
    AMBIGUOUS = "ambiguous"
    FALLBACK_EXPECTED = "fallback_expected"
    PROMPT_INJECTION = "prompt_injection"
    SYSTEM_PROMPT_EXTRACTION = "system_prompt_extraction"
    CROSS_ASSISTANT_LEAKAGE = "cross_assistant_leakage"
    CROSS_WORKSPACE_LEAKAGE = "cross_workspace_leakage"
    CROSS_ORGANISATION_LEAKAGE = "cross_organisation_leakage"
    MALICIOUS_MARKDOWN_HTML = "malicious_markdown_html"
    MALFORMED_INPUT = "malformed_input"
    SIMILAR_BUT_ABSENT = "similar_but_absent"
    IRRELEVANT_OFF_TOPIC = "irrelevant_off_topic"
    LONG_INPUT = "long_input"
    BENIGN_EDGE_CASE = "benign_edge_case"


class Answerability(str, Enum):
    ANSWERABLE = "answerable"
    UNANSWERABLE = "unanswerable"
    AMBIGUOUS = "ambiguous"


# Categories that attempt to cross a tenant/assistant boundary. The dataset case
# carries the attempted target scope in `metadata_json["cross_tenant_attempt"]`;
# the engine substitutes those identifiers for the run's own scope only for that
# one case and expects the real RAG orchestrator's existing tenant checks to
# reject it cleanly (see app.evaluation.engine).
ISOLATION_CATEGORIES = frozenset({
    CaseCategory.CROSS_ASSISTANT_LEAKAGE,
    CaseCategory.CROSS_WORKSPACE_LEAKAGE,
    CaseCategory.CROSS_ORGANISATION_LEAKAGE,
})

CASE_CATEGORY_VALUES = frozenset(member.value for member in CaseCategory)
ANSWERABILITY_VALUES = frozenset(member.value for member in Answerability)
