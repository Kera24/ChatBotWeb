"""Unit tests for app.ai.guardrails.evidence_sufficiency - the multi-signal
verifier that replaced grounding.py's single-chunk term-presence check to
close the specific similar_but_absent failure mode documented in
docs/04_Engineering/Similar_But_Absent_Five_Case_Baseline.md: a chunk that
coincidentally contains every extracted term in unrelated sentences.

End-to-end wiring into RAGOrchestrator.answer() and the real-embedding
results are covered by tests/test_rag_orchestrator.py and
Evidence_Sufficiency_Design.md respectively - this file tests the module's
decision logic in isolation.
"""

from app.ai.guardrails.evidence_sufficiency import (
    ExpectedValueType,
    evaluate_chunk_support,
    extract_requested_fact,
    extract_values,
    verify_evidence_sufficiency,
)
from app.ai.guardrails.reason_codes import GuardrailReasonCode

# --- requested-fact extraction ---

def test_extracts_entity_and_no_attribute_type_for_plain_question() -> None:
    fact = extract_requested_fact("Does the Starter plan include a dedicated account manager?")
    assert "Starter" in fact.entities


def test_detects_currency_attribute_type() -> None:
    fact = extract_requested_fact("How much does the Team plan cost per month?")
    assert fact.attribute_type == ExpectedValueType.CURRENCY


def test_detects_duration_attribute_type() -> None:
    fact = extract_requested_fact("How long is the money-back guarantee?")
    assert fact.attribute_type == ExpectedValueType.DURATION


def test_detects_date_attribute_type() -> None:
    fact = extract_requested_fact("When does my billing cycle renew?")
    assert fact.attribute_type == ExpectedValueType.DATE


def test_detects_numeric_attribute_type() -> None:
    fact = extract_requested_fact("How many recovery codes are generated?")
    assert fact.attribute_type == ExpectedValueType.NUMERIC


def test_falls_back_to_topic_keywords_when_no_entity() -> None:
    fact = extract_requested_fact("How long is a password reset link valid for?")
    assert fact.entities == ()
    assert "password" in fact.topic_keywords
    assert "reset" in fact.topic_keywords


def test_degenerate_duration_unit_entity_falls_back_to_keywords() -> None:
    # "month" would otherwise be extracted as an entity via grounding's
    # qualifier-root vocabulary, but a duration-unit word is degenerate as an
    # anchor for a DURATION question (see evidence_sufficiency.py's
    # _DURATION_UNIT_ENTITY_ROOTS docstring) - any value expressed in months
    # would trivially satisfy both the entity and the value check.
    fact = extract_requested_fact("How long is the money-back guarantee for a monthly subscription?")
    assert fact.entities == ()
    assert fact.attribute_type == ExpectedValueType.DURATION


def test_off_topic_detected_only_with_weak_score_and_no_signal() -> None:
    fact = extract_requested_fact("What programming language should I learn first?", best_retrieval_score=0.27)
    assert fact.off_topic_likely is True


def test_off_topic_not_flagged_with_strong_retrieval_score() -> None:
    fact = extract_requested_fact("What programming language should I learn first?", best_retrieval_score=0.6)
    assert fact.off_topic_likely is False


def test_off_topic_not_flagged_when_entity_present_even_with_weak_score() -> None:
    fact = extract_requested_fact("What does the Pricing Plans document say?", best_retrieval_score=0.2)
    assert fact.off_topic_likely is False


# --- value extraction ---

def test_extract_values_currency_accepts_dollar_and_percentage() -> None:
    assert extract_values("It costs $29 per month.", ExpectedValueType.CURRENCY)
    assert extract_values("Saves 20% compared to monthly.", ExpectedValueType.CURRENCY)


def test_extract_values_duration_accepts_hyphenated_form() -> None:
    assert extract_values("Covered by a 14-day money-back guarantee.", ExpectedValueType.DURATION)


def test_extract_values_duration_accepts_word_numbers() -> None:
    assert extract_values("ten single-use recovery codes are generated", ExpectedValueType.NUMERIC)


def test_extract_values_numeric_requires_unit_hint() -> None:
    # A bare digit near unrelated context (a version string, an hour range)
    # must not count as satisfying a numeric-value request.
    assert not extract_values("Support Policy Update v2.3, 24/7 coverage", ExpectedValueType.NUMERIC)
    assert extract_values("allows 300 requests per minute", ExpectedValueType.NUMERIC)


def test_extract_values_date_accepts_relative_phrasing() -> None:
    assert extract_values("Billing occurs on the anniversary of the signup date.", ExpectedValueType.DATE)


# --- chunk-level support evaluation ---

def test_direct_support_same_sentence() -> None:
    fact = extract_requested_fact("What is the refund policy for annual subscriptions?")
    outcome = evaluate_chunk_support(fact, "Annual subscribers get a 30-day refund window.", "Refund Policy")
    assert outcome.outcome == "direct_support"


def test_common_term_collision_does_not_produce_direct_support() -> None:
    # "Starter" coincidentally appears in a pricing sentence, unrelated to the
    # trash-retention fact actually being asked about - this is the exact
    # failure mode evidence_sufficiency was built to close.
    fact = extract_requested_fact("How many days does Northwind keep files in the trash for the Starter plan specifically?")
    outcome = evaluate_chunk_support(fact, "Northwind Cloud Storage offers four plans. Starter costs $9 per month.", "Pricing Plans")
    assert outcome.outcome != "direct_support"


def test_weak_single_term_match_against_unrelated_sentence() -> None:
    fact = extract_requested_fact("Does API v3 have a published rate limit for Enterprise customers specifically?")
    outcome = evaluate_chunk_support(fact, "Business and Enterprise tier customers now receive 24/7 support coverage.", "Support Policy Update")
    assert outcome.outcome != "direct_support"


def test_adjacent_sentence_evidence_still_supports() -> None:
    fact = extract_requested_fact("As a Business tier customer, what support hours do I get?")
    content = "Business and Enterprise tier customers now receive 24/7 support coverage. Starter and Team tier customers remain on standard hours."
    outcome = evaluate_chunk_support(fact, content, "Support Policy Update")
    assert outcome.outcome == "direct_support"


def test_no_entity_no_attribute_trivially_supported() -> None:
    fact = extract_requested_fact("Can you help me understand my account?")
    outcome = evaluate_chunk_support(fact, "Anything at all.", "Some Document")
    assert outcome.outcome == "direct_support"


# --- top-level verifier ---

def test_verify_sufficient_when_fact_present() -> None:
    verdict = verify_evidence_sufficiency(
        question="How long is the money-back guarantee for a monthly subscription?",
        chunk_contents=["Monthly subscription customers are covered by a 14-day money-back guarantee."],
        chunk_titles=["Refund Policy"],
        retrieval_scores=[0.6],
    )
    assert verdict.sufficient is True
    assert verdict.reason_code == GuardrailReasonCode.SUFFICIENT_EVIDENCE


def test_verify_requested_fact_absent() -> None:
    verdict = verify_evidence_sufficiency(
        question="What is the refund policy for annual subscriptions?",
        chunk_contents=[
            "Monthly subscription customers are covered by a 14-day money-back guarantee.",
            "Customers may choose monthly or annual billing. Annual billing saves 20% compared to paying monthly.",
        ],
        chunk_titles=["Refund Policy for Monthly Subscriptions", "Billing Cycles and Payment"],
        retrieval_scores=[0.6, 0.4],
    )
    assert verdict.sufficient is False
    assert verdict.reason_code == GuardrailReasonCode.REQUESTED_FACT_ABSENT


def test_verify_off_topic_question() -> None:
    verdict = verify_evidence_sufficiency(
        question="What programming language should I learn first?",
        chunk_contents=["Bucket names must be lowercase alphanumeric.", "API v1 was deprecated in January 2025."],
        chunk_titles=["Storage Bucket Naming Conventions", "API Versioning Policy"],
        retrieval_scores=[0.27, 0.25],
    )
    assert verdict.sufficient is False
    assert verdict.reason_code == GuardrailReasonCode.RELATED_TOPIC_ONLY


def test_verify_no_authorised_evidence() -> None:
    verdict = verify_evidence_sufficiency(question="What is the refund window?", chunk_contents=[], chunk_titles=[])
    assert verdict.sufficient is False
    assert verdict.reason_code == GuardrailReasonCode.NO_AUTHORISED_EVIDENCE


def test_verify_benign_paraphrase_with_no_exact_wording_overlap_still_passes() -> None:
    verdict = verify_evidence_sufficiency(
        question="If I refer to it as the 'Team tier', how much storage comes with it?",
        chunk_contents=["Team costs $29 per month and includes 1TB of storage for up to 10 members."],
        chunk_titles=["Pricing Plans"],
        retrieval_scores=[0.5],
    )
    assert verdict.sufficient is True


def test_verify_multi_sentence_supporting_evidence_passes() -> None:
    verdict = verify_evidence_sufficiency(
        question="As a Business tier customer, what support hours do I get and is that different from Starter?",
        chunk_contents=["Business and Enterprise tier customers now receive 24/7 support coverage. Starter and Team tier customers remain on standard support hours of 9am to 6pm."],
        chunk_titles=["Support Policy Update"],
        retrieval_scores=[0.5],
    )
    assert verdict.sufficient is True
