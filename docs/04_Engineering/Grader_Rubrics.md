# Grader Rubrics (version-controlled specification)

`RUBRIC_VERSION = "v1"` (`apps/api/app/evaluation/graders/rubrics.py`). This
document is the human-readable version of that module - the two must be
kept in sync; `rubrics.py` is what prompts/engine.py actually consume.

Every dimension below is **advisory**, not launch-gating, at introduction.
See [Grader_Architecture.md](./Grader_Architecture.md)'s "Advisory vs
gating policy" for what would need to be true before that changes for any
dimension. None of these graders replace the deterministic, launch-critical
checks from the prior guardrails cycle - isolation checks
(`app/access/widget_admin`), citation authorisation
(`app/ai/guardrails/citation_policy.py`), retrieval metrics
(`app/evaluation/metrics/retrieval.py`), evidence sufficiency
(`app/ai/guardrails/evidence_sufficiency.py`), and the hard safety/launch
gates (`app/evaluation/scoring.py`, `app/evaluation/gate.py`) all remain
fully in force, computed independently, and never overridden by a grader
score.

| Dimension | Question | Score range | Pass threshold | Gating? |
|---|---|---|---|---|
| Relevance | Does the answer directly address the user's question? | 0.0-1.0 | 0.6 | No |
| Groundedness | Are factual claims supported by the supplied authorised evidence? | 0.0-1.0 | 0.8 | No (candidate after calibration) |
| Faithfulness | Does the answer avoid contradicting or extending beyond the evidence? | 0.0-1.0 | 0.8 | No |
| Completeness | Does the answer include the important expected points without unnecessary additions? | 0.0-1.0 | 0.6 | No |
| Citation support | Do cited sources actually support the claims they are attached to? | 0.0-1.0 | 0.8 | No (candidate after calibration) |
| Clarity | Is the answer understandable, organised and readable? | 0.0-1.0 | 0.6 | No |
| Directness | Is it concise and appropriately focused? | 0.0-1.0 | 0.5 | No |
| Fallback appropriateness | When evidence is insufficient, does the response avoid guessing and provide an appropriate fallback? | 0.0-1.0 | 0.6 | No (candidate after calibration) |
| Clarification quality | When the question is ambiguous, does the assistant request the right missing information? | 0.0-1.0 | 0.5 | No |

For each dimension's full rubric text, applicability condition, and
strong/weak/invalid examples, see the corresponding `RubricDefinition` in
`app/evaluation/graders/rubrics.py` - reproduced in full below for
convenience.

## Relevance
**Rubric:** Score 1.0 if the answer directly addresses what was asked, using the specific entities/attributes named in the question. Score 0.0 if the answer is about a different topic or ignores the question. Partial credit for answering an adjacent-but-not-quite-asked question.
**Applies when:** `answer_state == "answered"`.
**Strong:** "How much does the Team plan cost?" -> "The Team plan costs $29 per month." **Weak:** answers with unrelated general info. **Invalid:** answer in a different language, or a non-answer.
**Limitations:** Cannot detect relevance for questions the grader itself misreads; not a substitute for the deterministic evidence-sufficiency check, which runs before generation.

## Groundedness
**Rubric:** Score 1.0 if every factual claim is directly traceable to the supplied evidence. Score 0.0 if the answer states facts not in the evidence at all. Evaluated against the evidence actually supplied to the grader, not the grader's world knowledge.
**Applies when:** `answer_state == "answered"`.
**Limitations:** A candidate to become gating after calibration - never overrides the deterministic evidence-sufficiency/citation checks.

## Faithfulness
**Rubric:** Score 1.0 if the answer neither contradicts the evidence nor extends beyond it with invented specifics. Distinct from groundedness: also penalises confident-sounding extrapolation even without a flatly false claim.
**Applies when:** `answer_state == "answered"`.
**Limitations:** Overlaps with groundedness by design - reported separately since they can disagree.

## Completeness
**Rubric:** Score 1.0 if the answer covers every important point available in the evidence that responds to the question, without padding with unrelated evidence.
**Applies when:** `answer_state == "answered"`.
**Limitations:** "Important" is a judgement call without a fixed checklist - most useful as a relative, human-reviewed signal.

## Citation support
**Rubric:** Score 1.0 if every citation's underlying chunk content actually supports the claim next to it. Grades *support*, not *authorisation* (authorisation is the separate, deterministic, zero-tolerance `citation_policy` check).
**Applies when:** `answer_state == "answered"` and citations are present.
**Limitations:** A candidate to become gating after calibration - never a substitute for the deterministic authorisation check.

## Clarity
**Rubric:** Score 1.0 for a clear, well-organised, readable answer, independent of factual correctness.
**Applies when:** `answer_state == "answered"`.
**Limitations:** Purely advisory/stylistic; never approved for gating.

## Directness
**Rubric:** Score 1.0 for an answer as short as it can be while fully answering the question.
**Applies when:** `answer_state == "answered"`.
**Limitations:** Some verbosity is appropriate for genuinely complex questions; purely advisory.

## Fallback appropriateness
**Rubric:** Applies only when `answer_state` is `fallback`/`failed`. Score 1.0 if the fallback clearly states the limitation without inventing a partial answer.
**Applies when:** `answer_state in ("fallback", "failed")`.
**Limitations:** A candidate to become gating (guessing-in-a-fallback is severe) - not gating today; the deterministic evidence-sufficiency check already prevents most guessing pre-generation.

## Clarification quality
**Rubric:** Applies only to `ambiguous`-category questions. Score 1.0 if the response identifies the specific missing detail rather than a generic "can you clarify?".
**Applies when:** `category == "ambiguous"`.
**Limitations:** The product has no dedicated `clarification_required` answer_state today (a documented gap from the guardrails cycle) - this grades whatever response was actually produced.
