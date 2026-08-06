"""Version-controlled grader rubric specification.

This is the code-form of the same specification documented in
docs/04_Engineering/Grader_Rubrics.md - the two must be kept in sync; this
module is the one actually consumed by prompts.py/engine.py, the doc is the
human-readable version-controlled reference. `RUBRIC_VERSION` bumps whenever
any rubric's scoring criteria changes (not for typo fixes).

Every dimension is advisory (non-launch-gating) at introduction per
Section 12 of the grader task: "groundedness and citation-support graders
may become gating only after successful human calibration; relevance,
clarity and directness remain advisory unless explicitly approved." No
dimension is currently marked gating=True - see Grader_Architecture.md's
"Advisory vs gating policy" section for the calibration threshold that would
need to be met before that changes, and app.evaluation.gate /
app.evaluation.scoring (deterministic, launch-critical, untouched by this
module) for what actually gates a release today.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

RUBRIC_VERSION = "v1"


class GraderDimension(str, Enum):
    RELEVANCE = "relevance"
    GROUNDEDNESS = "groundedness"
    FAITHFULNESS = "faithfulness"
    COMPLETENESS = "completeness"
    CITATION_SUPPORT = "citation_support"
    CLARITY = "clarity"
    DIRECTNESS = "directness"
    FALLBACK_APPROPRIATENESS = "fallback_appropriateness"
    CLARIFICATION_QUALITY = "clarification_quality"


@dataclass(frozen=True)
class RubricDefinition:
    dimension: GraderDimension
    question: str
    rubric: str
    score_range: tuple[float, float]
    pass_threshold: float
    gating: bool
    strong_example: str
    weak_example: str
    invalid_example: str
    limitations: str
    applicable_when: str


RUBRICS: dict[GraderDimension, RubricDefinition] = {
    GraderDimension.RELEVANCE: RubricDefinition(
        dimension=GraderDimension.RELEVANCE,
        question="Does the answer directly address the user's question?",
        rubric=(
            "Score 1.0 if the answer directly addresses what was asked, using the specific entities/attributes "
            "named in the question. Score 0.0 if the answer is about a different topic or ignores the question. "
            "Partial credit for answering an adjacent-but-not-quite-asked question."
        ),
        score_range=(0.0, 1.0), pass_threshold=0.6, gating=False,
        strong_example="Q: 'How much does the Team plan cost?' A: 'The Team plan costs $29 per month.' - directly answers.",
        weak_example="Q: 'How much does the Team plan cost?' A: 'Northwind offers several plans with different storage tiers.' - topically related, doesn't answer.",
        invalid_example="An answer in a different language than the question, or a non-answer like 'I am an AI assistant.'",
        limitations="Cannot detect relevance for questions the grader itself misreads; not a substitute for the deterministic evidence-sufficiency check, which runs before generation, not after.",
        applicable_when="answer_state == 'answered'",
    ),
    GraderDimension.GROUNDEDNESS: RubricDefinition(
        dimension=GraderDimension.GROUNDEDNESS,
        question="Are factual claims supported by the supplied authorised evidence?",
        rubric=(
            "Score 1.0 if every factual claim in the answer is directly traceable to the supplied evidence. "
            "Score 0.0 if the answer states facts (numbers, dates, names, policies) that do not appear in the evidence at all. "
            "This is about the evidence actually supplied to the grader, not the grader's own world knowledge - "
            "a factually true statement not present in the evidence is still ungrounded for this rubric."
        ),
        score_range=(0.0, 1.0), pass_threshold=0.8, gating=False,
        strong_example="Evidence: 'Team costs $29/month.' Answer: 'The Team plan is $29 per month.' - grounded.",
        weak_example="Evidence: 'Team costs $29/month.' Answer: 'The Team plan is $29 per month, a great value.' - the value judgement is an ungrounded addition.",
        invalid_example="Answer states a specific number/date not present anywhere in the evidence.",
        limitations="A candidate to become gating after calibration (see Grader_Architecture.md), but is not gating today - never overrides the deterministic evidence-sufficiency/citation checks, which remain authoritative for launch decisions.",
        applicable_when="answer_state == 'answered'",
    ),
    GraderDimension.FAITHFULNESS: RubricDefinition(
        dimension=GraderDimension.FAITHFULNESS,
        question="Does the answer avoid contradicting or extending beyond the evidence?",
        rubric=(
            "Score 1.0 if the answer neither contradicts the evidence nor extends beyond it with invented specifics. "
            "Score 0.0 if the answer contradicts a stated fact, or states a specific fee/date/policy/condition the "
            "evidence does not contain. Distinct from groundedness: faithfulness also penalises confident-sounding "
            "extrapolation ('this likely also applies to...') even when no single claim is flatly false."
        ),
        score_range=(0.0, 1.0), pass_threshold=0.8, gating=False,
        strong_example="Evidence: 'Refunds within 14 days.' Answer: 'You have 14 days to request a refund.' - faithful.",
        weak_example="Evidence: 'Refunds within 14 days.' Answer: 'You likely have about two weeks, possibly longer for annual plans.' - unfaithful extrapolation.",
        invalid_example="Answer directly contradicts a number/date/condition stated in the evidence.",
        limitations="Overlaps with groundedness by design (two views of the same underlying failure mode) - reported separately since they can disagree (e.g. a claim can be grounded but phrased in a way that overstates certainty).",
        applicable_when="answer_state == 'answered'",
    ),
    GraderDimension.COMPLETENESS: RubricDefinition(
        dimension=GraderDimension.COMPLETENESS,
        question="Does the answer include the important expected points without unnecessary additions?",
        rubric=(
            "Score 1.0 if the answer covers every important point available in the evidence that responds to the "
            "question, without padding with unrelated evidence. Score 0.0 if it omits a clearly important, directly "
            "relevant point that was available in the supplied evidence, or pads heavily with irrelevant detail."
        ),
        score_range=(0.0, 1.0), pass_threshold=0.6, gating=False,
        strong_example="Q asks for price and storage; evidence has both; answer states both.",
        weak_example="Q asks for price and storage; evidence has both; answer states only price.",
        invalid_example="Answer copies unrelated evidence paragraphs wholesale, unrelated to the question asked.",
        limitations="'Important' is a judgement call the grader makes without a fixed checklist - most useful as a relative, human-reviewed signal, not an absolute score.",
        applicable_when="answer_state == 'answered'",
    ),
    GraderDimension.CITATION_SUPPORT: RubricDefinition(
        dimension=GraderDimension.CITATION_SUPPORT,
        question="Do cited sources actually support the claims they are attached to?",
        rubric=(
            "Score 1.0 if every citation's underlying chunk content actually supports the claim next to it. "
            "Score 0.0 if a citation is attached to a claim the cited chunk does not address at all. "
            "This grades *support*, not *authorisation* - citation authorisation (is this chunk one the assistant "
            "was even allowed to retrieve) is a separate, deterministic, zero-tolerance check "
            "(app.ai.guardrails.citation_policy) that this grader never overrides."
        ),
        score_range=(0.0, 1.0), pass_threshold=0.8, gating=False,
        strong_example="Claim: '$29/month.' Cited chunk: 'Team costs $29 per month.' - supported.",
        weak_example="Claim: '$29/month.' Cited chunk: is the Refund Policy document, unrelated to pricing.",
        invalid_example="A citation index that does not correspond to any supplied evidence chunk.",
        limitations="A candidate to become gating after calibration - never a substitute for the deterministic citation_policy authorisation check, which remains a zero-tolerance hard gate regardless of this grader's output (see Section 12).",
        applicable_when="answer_state == 'answered' and citations present",
    ),
    GraderDimension.CLARITY: RubricDefinition(
        dimension=GraderDimension.CLARITY,
        question="Is the answer understandable, organised and readable?",
        rubric=(
            "Score 1.0 for a clear, well-organised, easy-to-read answer. Score 0.0 for an answer that is garbled, "
            "self-contradictory in phrasing, or so disorganised the reader cannot follow it, independent of whether "
            "the underlying facts are correct."
        ),
        score_range=(0.0, 1.0), pass_threshold=0.6, gating=False,
        strong_example="A short, well-structured answer with the requested fact stated plainly.",
        weak_example="A run-on answer that buries the actual fact in the middle of an unrelated paragraph.",
        invalid_example="Garbled or truncated text, mismatched markup, repeated sentences.",
        limitations="Purely advisory - stylistic, not a safety or correctness signal; never approved for gating per Section 12.",
        applicable_when="answer_state == 'answered'",
    ),
    GraderDimension.DIRECTNESS: RubricDefinition(
        dimension=GraderDimension.DIRECTNESS,
        question="Is it concise and appropriately focused?",
        rubric=(
            "Score 1.0 for an answer that is as short as it can be while still fully answering the question. "
            "Score 0.0 for an answer padded with disclaimers, repetition, or restating the question at length "
            "before getting to the point."
        ),
        score_range=(0.0, 1.0), pass_threshold=0.5, gating=False,
        strong_example="'The Team plan costs $29 per month.'",
        weak_example="'That's a great question! Let me tell you about our plans. Northwind offers several tiers... the Team plan, specifically, costs $29 per month, which I hope helps!'",
        invalid_example="An answer that never reaches the actual fact.",
        limitations="Purely advisory - some verbosity is appropriate for genuinely complex multi-part questions; never approved for gating per Section 12.",
        applicable_when="answer_state == 'answered'",
    ),
    GraderDimension.FALLBACK_APPROPRIATENESS: RubricDefinition(
        dimension=GraderDimension.FALLBACK_APPROPRIATENESS,
        question="When evidence is insufficient, does the response avoid guessing and provide an appropriate fallback?",
        rubric=(
            "Applies only when answer_state is 'fallback'/'failed' (or expected_answerability is 'unanswerable'). "
            "Score 1.0 if the fallback response clearly and politely states the limitation without inventing a "
            "partial answer, and (when configured) points to a human-contact option. Score 0.0 if the fallback text "
            "itself leaks a guessed fact, is confusing, or is an unhelpful bare refusal with no guidance at all."
        ),
        score_range=(0.0, 1.0), pass_threshold=0.6, gating=False,
        strong_example="'The knowledge base doesn't contain that specific detail. Please contact support for details.'",
        weak_example="'I don't know, but it's probably similar to the monthly plan.' - a guess disguised as a fallback.",
        invalid_example="A fallback response containing a specific invented number/date/policy.",
        limitations="A candidate to become gating after calibration (guessing-in-a-fallback is a severe failure mode) - not gating today; the deterministic evidence-sufficiency check already prevents most guessing before generation runs.",
        applicable_when="answer_state in ('fallback', 'failed')",
    ),
    GraderDimension.CLARIFICATION_QUALITY: RubricDefinition(
        dimension=GraderDimension.CLARIFICATION_QUALITY,
        question="When the question is ambiguous, does the assistant request the right missing information?",
        rubric=(
            "Applies only to ambiguous-category questions. Score 1.0 if the response identifies the specific "
            "missing detail needed to answer (e.g. which plan tier) rather than a generic 'can you clarify?'. "
            "Score 0.0 if the response guesses an answer to an ambiguous question instead of asking, or asks a "
            "question unrelated to what is actually ambiguous."
        ),
        score_range=(0.0, 1.0), pass_threshold=0.5, gating=False,
        strong_example="Q: 'How much storage do I get?' (no plan named) A: 'Which plan are you on - Starter, Team, Business, or Enterprise? Storage varies by tier.'",
        weak_example="Q: 'How much storage do I get?' A: 'Can you clarify your question?' - vague, doesn't name the missing detail.",
        invalid_example="Answers with a specific number despite the question being genuinely ambiguous between multiple tiers.",
        limitations="Purely advisory; the product does not currently have a dedicated 'clarification_required' answer_state (see Guardrails_Task_Specification.md's documented gap) so this grades whatever response was actually produced for ambiguous-category cases today.",
        applicable_when="category == 'ambiguous'",
    ),
}


def get_rubric(dimension: GraderDimension) -> RubricDefinition:
    return RUBRICS[dimension]


def gating_dimensions() -> tuple[GraderDimension, ...]:
    return tuple(dim for dim, rubric in RUBRICS.items() if rubric.gating)


def advisory_dimensions() -> tuple[GraderDimension, ...]:
    return tuple(dim for dim, rubric in RUBRICS.items() if not rubric.gating)
