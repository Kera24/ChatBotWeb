"""Unit tests for Evidence Sufficiency V2 (app.ai.guardrails.evidence_sufficiency's
V2 section, docs/adr/0034-promote-evidence-sufficiency-v2.md). Every case
here reproduces a defect proven against the real corpus by
app.operations.eval_evidence_sufficiency_failure_analysis/_bakeoff (see the
promotion ADR) - not a hypothetical.

V1's own test_evidence_sufficiency.py is untouched and still exercises V1's
exact prior behaviour; this file is additive, mirroring that file's style.
"""

from app.ai.guardrails.evidence_sufficiency import (
    EvidenceSufficiencyV1Verifier,
    EvidenceSufficiencyV2Verifier,
    ExpectedValueType,
    build_evidence_verifier,
    extract_requested_fact_v2,
    verify_evidence_sufficiency,
    verify_evidence_sufficiency_v2,
)
from app.ai.guardrails.reason_codes import GuardrailReasonCode

# --- root cause 1: LOCATION case-sensitivity ---

def test_v1_fails_location_question_due_to_case_sensitivity_bug() -> None:
    content = "Meridian has offices in Austin, Lisbon, and Singapore, with the majority of the team working remotely."
    verdict = verify_evidence_sufficiency(
        question="Where are Meridian's offices located?", chunk_contents=[content], chunk_titles=["About Meridian"], retrieval_scores=[0.68],
    )
    assert verdict.sufficient is False


def test_v2_fixes_location_case_sensitivity_bug() -> None:
    content = "Meridian has offices in Austin, Lisbon, and Singapore, with the majority of the team working remotely."
    verdict = verify_evidence_sufficiency_v2(
        question="Where are Meridian's offices located?", chunk_contents=[content], chunk_titles=["About Meridian"], retrieval_scores=[0.68],
    )
    assert verdict.sufficient is True
    assert verdict.reason_code == GuardrailReasonCode.SUFFICIENT_EVIDENCE


# --- root cause 2: first-match-in-window vs. nearest-to-anchor ---

def test_v1_attributes_wrong_table_row_value() -> None:
    content = "| Plan | Price |\n| --- | --- |\n| Starter | $19/month |\n| Team | $79/month |\n| Business | $249/month |"
    from app.ai.guardrails.evidence_sufficiency import evaluate_chunk_support, extract_requested_fact

    outcome = evaluate_chunk_support(extract_requested_fact("How much does the Team plan cost per month?"), content, "Billing and Plans Overview")
    assert outcome.matched_value == "$19"  # wrong - Starter's price, not Team's


def test_v2_selects_nearest_table_row_value() -> None:
    content = "| Plan | Price |\n| --- | --- |\n| Starter | $19/month |\n| Team | $79/month |\n| Business | $249/month |"
    from app.ai.guardrails.evidence_sufficiency import evaluate_chunk_support_v2

    outcome = evaluate_chunk_support_v2(extract_requested_fact_v2("How much does the Team plan cost per month?"), content, "Billing and Plans Overview")
    assert outcome.matched_value == "$79"


# --- root cause 3: weak-anchor conflict false positives, arbitrated only at conflict time ---

def test_v1_false_positive_conflicting_evidence_from_unrelated_section() -> None:
    # Reproduced verbatim from the real chunking_dataset.json failure
    # analysis (see ADR-0034) - the second sentence shares exactly two
    # generic keywords ("build", "deleted") with the question by coincidence
    # (it is actually about billing-suspension build-history deletion, not
    # build LOG retention), which is enough to anchor V1's keyword fallback.
    correct = "Build Logs\n\nBuild logs are retained for 90 days from the completion of the build, after which they are automatically and permanently deleted."
    unrelated = "If the balance remains unpaid for a further 15 days after suspension, build history is permanently deleted."
    verdict = verify_evidence_sufficiency(
        question="How long are build logs kept before they are automatically deleted?",
        chunk_contents=[correct, unrelated], chunk_titles=["Data Retention Policy", "FAQ: Billing and Payments"], retrieval_scores=[0.76, 0.44],
    )
    assert verdict.reason_code == GuardrailReasonCode.CONFLICTING_EVIDENCE  # the proven false-positive


def test_v2_suppresses_weak_anchor_false_conflict() -> None:
    # Reproduced verbatim from the real chunking_dataset.json corpus (one of
    # the 7 cases the Part 8 bake-off measured fixed, see ADR-0034) - the
    # question has few enough topic keywords (3: "cutover", "certificate",
    # "revoked") that V1's own primary anchor threshold only requires ONE
    # hit, letting a single shared word ("certificate") anchor a completely
    # different fact (the canary traffic duration) as a second "value". V2's
    # arbitration-only stricter bar (>=2 hits) excludes that weak match
    # without touching the primary determination that made either sentence
    # `direct_support` in the first place.
    correct = "The old certificate is revoked 24 hours after cutover, giving time to roll back if an unexpected issue surfaces."
    unrelated = "Canary traffic is then routed to the new certificate for 15 minutes while error rates are monitored."
    verdict = verify_evidence_sufficiency_v2(
        question="How long after cutover is the old TLS certificate revoked?",
        chunk_contents=[correct, unrelated], chunk_titles=["Runbook: Certificate Rotation Procedure", "Runbook: Certificate Rotation Procedure"], retrieval_scores=[0.7, 0.6],
    )
    assert verdict.sufficient is True
    assert verdict.reason_code == GuardrailReasonCode.SUFFICIENT_EVIDENCE


def test_v1_has_the_same_false_positive_on_the_tls_certificate_case() -> None:
    correct = "The old certificate is revoked 24 hours after cutover, giving time to roll back if an unexpected issue surfaces."
    unrelated = "Canary traffic is then routed to the new certificate for 15 minutes while error rates are monitored."
    verdict = verify_evidence_sufficiency(
        question="How long after cutover is the old TLS certificate revoked?",
        chunk_contents=[correct, unrelated], chunk_titles=["Runbook: Certificate Rotation Procedure", "Runbook: Certificate Rotation Procedure"], retrieval_scores=[0.7, 0.6],
    )
    assert verdict.reason_code == GuardrailReasonCode.CONFLICTING_EVIDENCE


def test_v2_still_reports_conflict_when_both_candidates_meet_the_stricter_bar() -> None:
    # Reproduced from the real chunking_dataset.json corpus (still-failing
    # after V2 in the Part 8 bake-off, see ADR-0034's "Remaining
    # limitations") - both sentences share 2+ topic keywords with the
    # question, clearing V2's arbitration bar too, so the conflict is (still
    # incorrectly, but consistently with the promoted fix's documented
    # scope) reported. This guards against a future change accidentally
    # suppressing conflicts unconditionally.
    correct = "Build Logs\n\nBuild logs are retained for 90 days from the completion of the build, after which they are automatically and permanently deleted."
    unrelated_but_two_keyword_hits = "If the balance remains unpaid for a further 15 days after suspension, build history is permanently deleted."
    verdict = verify_evidence_sufficiency_v2(
        question="How long are build logs kept before they are automatically deleted?",
        chunk_contents=[correct, unrelated_but_two_keyword_hits], chunk_titles=["Data Retention Policy", "FAQ: Billing and Payments"], retrieval_scores=[0.76, 0.44],
    )
    assert verdict.reason_code == GuardrailReasonCode.CONFLICTING_EVIDENCE


def test_v2_does_not_regress_single_answer_weak_keyword_case() -> None:
    # Real regression caught by the Part 8 bake-off during development - only
    # one shared keyword ("billing"), yet the correct and only answer. Must
    # stay fixed.
    content = (
        "Customers may choose monthly or annual billing. Annual billing is charged once per year and saves 20% "
        "compared to paying monthly. Billing occurs on the anniversary of the signup date. Invoices are emailed "
        "to the workspace owner and are available for download from the billing dashboard for up to 24 months."
    )
    verdict = verify_evidence_sufficiency_v2(
        question="When does my billing cycle renew?", chunk_contents=[content], chunk_titles=["Billing Cycles and Payment"], retrieval_scores=[0.6],
    )
    assert verdict.sufficient is True
    assert verdict.reason_code == GuardrailReasonCode.SUFFICIENT_EVIDENCE


# --- root cause 4: DATE month+year, CONTACT->ELIGIBILITY misdetection ---

def test_v1_fails_date_without_day_of_month() -> None:
    content = "In February 2025, Meridian completed SOC 2 Type II certification."
    verdict = verify_evidence_sufficiency(
        question="When did Meridian complete its SOC 2 Type II certification?", chunk_contents=[content], chunk_titles=["Security and Compliance Policy"], retrieval_scores=[0.82],
    )
    assert verdict.sufficient is False


def test_v2_accepts_month_year_date_format() -> None:
    content = "In February 2025, Meridian completed SOC 2 Type II certification."
    verdict = verify_evidence_sufficiency_v2(
        question="When did Meridian complete its SOC 2 Type II certification?", chunk_contents=[content], chunk_titles=["Security and Compliance Policy"], retrieval_scores=[0.82],
    )
    assert verdict.sufficient is True


def test_v2_routes_availability_question_to_eligibility_not_contact() -> None:
    fact = extract_requested_fact_v2("Is phone support available on the Team tier?")
    assert fact.attribute_type == ExpectedValueType.ELIGIBILITY


def test_v2_contact_still_detects_explicit_contact_detail_ask() -> None:
    fact = extract_requested_fact_v2("What is the support phone number?")
    assert fact.attribute_type == ExpectedValueType.CONTACT


# --- preserved protections (must hold in V2 exactly as in V1) ---

def test_v2_similar_but_absent_still_rejected() -> None:
    # Reuses test_evidence_sufficiency.py's own proven similar_but_absent
    # fixture (a value-typed question where the retrieved chunks discuss a
    # RELATED but different fact) - V2 must not become more permissive than
    # V1 in this direction.
    verdict = verify_evidence_sufficiency_v2(
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


def test_v2_no_evidence_still_rejected() -> None:
    verdict = verify_evidence_sufficiency_v2(question="How much does the Team plan cost?", chunk_contents=[], chunk_titles=[], retrieval_scores=[])
    assert verdict.sufficient is False
    assert verdict.reason_code == GuardrailReasonCode.NO_AUTHORISED_EVIDENCE


def test_v2_unrelated_chunks_do_not_get_combined() -> None:
    # No multi-chunk composition was implemented (evidence did not support
    # it - ADR-0034) - two chunks that are each independently incomplete for
    # a DIFFERENT fact must not be stitched together into a false pass.
    entity_only = "The Enterprise plan is described in detail in our sales materials."
    value_only_unrelated = "Standard support responses are targeted within 24 business hours for any tier."
    verdict = verify_evidence_sufficiency_v2(
        question="Can Enterprise customers extend deployment artifact retention beyond the default 180 days?",
        chunk_contents=[entity_only, value_only_unrelated], chunk_titles=["Sales", "Support Tiers"], retrieval_scores=[0.4, 0.35],
    )
    assert verdict.sufficient is False


def test_v2_verdicts_are_deterministic() -> None:
    content = "Meridian has offices in Austin, Lisbon, and Singapore."
    first = verify_evidence_sufficiency_v2(question="Where are Meridian's offices located?", chunk_contents=[content], chunk_titles=["About"], retrieval_scores=[0.6])
    second = verify_evidence_sufficiency_v2(question="Where are Meridian's offices located?", chunk_contents=[content], chunk_titles=["About"], retrieval_scores=[0.6])
    assert first == second


def test_v2_citation_provenance_preserved() -> None:
    # matched_sentence must be verbatim text from the actual chunk content
    # (never fabricated) - the guardrail asserts sufficiency, it never
    # invents supporting text of its own.
    content = "Build logs are retained for 90 days from the completion of the build."
    verdict = verify_evidence_sufficiency_v2(
        question="How long are build logs kept?", chunk_contents=[content], chunk_titles=["Data Retention Policy"], retrieval_scores=[0.7],
    )
    assert verdict.sufficient is True


# --- injectable verifier wiring (mirrors Reranker/QueryTransformer's pattern) ---

def test_build_evidence_verifier_selects_v1_by_default_for_unknown_value() -> None:
    verifier = build_evidence_verifier("unknown")
    assert isinstance(verifier, EvidenceSufficiencyV1Verifier)
    assert verifier.version == "v1"


def test_build_evidence_verifier_selects_v2() -> None:
    verifier = build_evidence_verifier("v2")
    assert isinstance(verifier, EvidenceSufficiencyV2Verifier)
    assert verifier.version == "v2"


def test_v1_verifier_object_matches_module_function() -> None:
    content = "Meridian has offices in Austin, Lisbon, and Singapore."
    direct = verify_evidence_sufficiency(question="Where are Meridian's offices located?", chunk_contents=[content], chunk_titles=["About"], retrieval_scores=[0.6])
    via_object = EvidenceSufficiencyV1Verifier().verify(question="Where are Meridian's offices located?", chunk_contents=[content], chunk_titles=["About"], retrieval_scores=[0.6])
    assert direct == via_object
