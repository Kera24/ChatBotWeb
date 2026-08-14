# ADR-0034: Promote Evidence Sufficiency V2

Status: Accepted
Date: 2026-08-13

## Context

ADR-0033 concluded that `hybrid_rrf`, reranking, and (separately, `docs/future/QueryRewrite.md`'s Phase 3 bake-off) deterministic query rewriting do not materially improve the real 104-case `chunking_dataset.json` corpus, and flagged as a future reconsideration trigger that `app.ai.guardrails.evidence_sufficiency`'s value-extraction limitations were "masking a small part of either [retrieval] arm's true recall." This task is that follow-up: a full case-level failure analysis (`app.operations.eval_evidence_sufficiency_failure_analysis`) over both `golden_dataset.json` and `chunking_dataset.json`, real embeddings (`nomic-embed-text-v2-moe`), the exact validated retrieval stack held constant (`structure_aware` chunking, `dense_only`, threshold 0.32 — ADR-0031/0032), confirms the hypothesis: on the chunking corpus, 26 of 83 answerable cases (31.3%) where the expected document was already retrieved into the final context still failed at the evidence-sufficiency guardrail layer — a "evidence-present-but-rejected" rate consistent with ADR-0033's suspicion. The golden corpus showed almost none (1/35, 2.9%), consistent with its documents being shorter than one chunk each.

Inspecting the actual retrieved chunk content and the verifier's own `ChunkSupportOutcome`s (not assumption) for every one of the 26 chunking-corpus cases found three concrete, reproducible defects, not a diffuse quality problem:

1. **Case-sensitivity bug**: `evaluate_chunk_support` extracts values from an already-lowercased window, silently defeating any pattern requiring an uppercase first letter — `ExpectedValueType.LOCATION`'s `[A-Z][a-zA-Z]+` could never match a real city/region name, 100% of the time, regardless of whether it was actually present.
2. **First-match bug**: a markdown pricing table with no terminal punctuation collapses into one "sentence"; the verifier took `values[0]` — the first typed value anywhere in the window — rather than the value nearest the matched entity, so a question about the Team plan's price could be silently attributed the Starter row's price.
3. **Weak-anchor false collision**: when a question has no extractable entity, the keyword-fallback anchor required as few as one shared generic word (e.g. "days") to treat a chunk as supporting evidence. Across `chunking_dataset.json`'s deliberately multi-section policy documents, this repeatedly produced several spurious `direct_support` outcomes with *different* values for the same question, which the conflict check then reported as `conflicting_evidence` (Part 4's category F, "unrelated numeric collision" — not a genuine contradiction, supersession, or scope difference; inspection found **zero** genuine contradictions and **zero** genuine supersession/scope-difference cases among the 17 `conflicting_evidence` rejections analysed — the corpus's deliberately-authored SOC 2 Type I→Type II "superseded evidence" example did not even reach the conflict check, since its `DATE` extraction failed for reason 4 below).
4. Two smaller, independently-confirmed value-extraction gaps: `DATE` required a day-of-month and rejected the common "Month YYYY" form ("In February 2025, ..."); `CONTACT`'s trigger pattern fired on plain availability questions ("Is phone support available on the Team tier?"), routing them through a phone-number/email regex that could never match availability prose.

`docs/future/GuardrailsV2.md` had left the relationship between `evidence_sufficiency` and the unused `grounding.py` module as an open question pending evaluation data. This task's evaluation data answers a related, more urgent question first — `evidence_sufficiency` itself has fixable false-rejection defects — and did not touch `grounding.py`, which remains out of scope per that spec.

## Decision

**Promote Evidence Sufficiency V2 (`settings.EVIDENCE_VERIFIER_VERSION` default `"v1"` → `"v2"`).**

V2 (`app.ai.guardrails.evidence_sufficiency`'s V2 section) is additive: V1's function, dataclasses, and constants are completely unmodified, so every existing call site/test keeps its exact current behaviour if pinned back to `"v1"`. V2 fixes exactly the four defects above:

1. Extracts values from the original-case window text (anchor matching stays case-insensitive).
2. Splits markdown table rows as their own sentence-like unit and selects the value positioned nearest the matched anchor.
3. At conflict-arbitration time only (not the primary sufficiency determination — see below), requires at least `min(2, keyword_count)` shared keywords in a *second* candidate's own matched sentence before trusting it as a genuine competing value.
4. Extends `DATE` to accept "Month YYYY"; narrows `CONTACT`'s trigger to an explicit contact-detail ask and routes bare availability phrasing to `ELIGIBILITY`.

An initial version of fix 3 tightened the *primary* per-chunk keyword-anchor threshold (not just conflict arbitration), which regressed a real golden-corpus case ("When does my billing cycle renew?" / "Billing occurs on the anniversary of the signup date." — only one shared keyword, "billing", yet the correct and only answer). Caught by this task's own Part 8 bake-off, not assumed away — the primary threshold was reverted to match V1 exactly, and the stricter check was moved to apply only when arbitrating between multiple already-`direct_support` candidates with different values, which does not affect the single-answer case at all.

Explicitly **not** implemented, because the evidence did not support it ("implement X only if the failure analysis proves it is needed"):
- **Multi-chunk evidence composition** (Part 3): only one case across both corpora (35 + 83 = 118 evidence-present cases) needed combining two documents' facts, and it is in `golden_dataset.json`, not the corpus purpose-built for multi-chunk documents — every `multi_document`-category case in `chunking_dataset.json` already passes today without composition. n=1 does not justify the bounded-composition mechanism Part 3 describes; documented here as a known, low-frequency gap instead.
- **Semantic/paraphrase fallback** (Part 6): no rejection traced to a lexical-only miss once the four defects above were accounted for — the one paraphrase-tagged rejection remaining (`entity_mismatch`, "Does Meridian offer SMS-based two-factor authentication?") is a genuine distinctive-term-extraction mismatch (the source never says "SMS-based"), not something a bounded semantic-similarity check was proven to fix here.
- **Clarification answer state** (Part 7): the dataset already models "answerable only after clarification" as `category=ambiguous` + `expected_answerability=ambiguous` (+ `tags: ["clarification-needed"]`, `metadata_json.expected_clarification` where authored) and both corpora already pass 100% of `ambiguous`-category cases under both V1 and V2 by correctly falling back — the existing fallback IS the correct behaviour these cases need today; the response contract has no distinct "ask a clarifying question and wait" outcome, and adding one is a chat-protocol change out of this task's scope. Documented as design-only, per this task's explicit instruction.

### Evidence (Part 8 bake-off: `app.operations.eval_evidence_sufficiency_bakeoff --real`)

Real embeddings throughout, same corpus/chunking/retrieval/threshold/prompts/generation/citations for both arms — only `EVIDENCE_VERIFIER_VERSION` varies.

**Golden dataset**: pass rate 93.98% both arms (byte-identical), hard failures 0/0, citation coverage 100%/100%. Per-category pass rate is **identical in every one of 17 categories**, including every isolation category (`cross_assistant_leakage`/`cross_workspace_leakage`/`cross_organisation_leakage`: 100%/100%), `prompt_injection`/`system_prompt_extraction`/`malicious_markdown_html` (100%/100%), and `similar_but_absent`/`unanswerable` (100%/100%). Zero transitions besides the one already-known, out-of-scope multi-chunk case (`unchanged_fail`, both arms).

**Chunking dataset** (the corpus that matters most for this decision — same rationale ADR-0033 used): pass rate **63.46% → 70.19%** (+6.7pp), `answerable_factual` category **66.2% → 75.3%**, hard failures **10 → 10** (unchanged), citation coverage **100% → 100%** (unchanged), `similar_but_absent`/`unanswerable`/`ambiguous`/`irrelevant_off_topic`/`benign_edge_case`/`multi_document` category pass rates **all unchanged**. Of the 26 evidence-present-but-rejected cases the failure analysis identified: **7 fixed, 0 newly broken**, 19 still fail (mostly the weak-anchor conflict false positives fix 3 only partially resolves — see Remaining limitations). Evidence-present-but-rejected rate: 31.3% → 22.9% (a 27% relative reduction).

### Part 10 promotion criteria — checked against the evidence above

| Criterion | Result |
|---|---|
| Answerable pass rate materially improves | ✅ chunking +9.1pp (`answerable_factual`); golden unchanged (had almost no room) |
| Evidence-present-but-rejected rate drops materially | ✅ 31.3%→22.9% on chunking (the corpus with a real rate to move) |
| Zero new isolation/citation failures | ✅ confirmed identical category pass rates both corpora |
| Zero new secret/safety hard failures | ✅ hard_failure_cases unchanged in both corpora |
| Similar-but-absent protection remains strong | ✅ unchanged both corpora (chunking's 0.0% rate is **pre-existing**, identical in both arms — a dataset/generation-mode issue unrelated to this change, see Remaining limitations, not touched by this task) |
| Unanswerable false-answer rate does not regress | ✅ unchanged both corpora |
| No significant false-positive evidence acceptance | ✅ zero `newly_broken` transitions, hard failures unchanged |
| Deterministic/explainable | ✅ pure regex/structural, no LLM, identical architecture to V1 |

All eight criteria are met with real, measured evidence. Promoted.

## Alternatives

- **Promote V2 but keep the stricter primary keyword threshold from the first draft of fix 3** — rejected: directly caused a real regression (billing-cycle-renewal case), caught by this task's own bake-off before being shipped.
- **Do not promote; leave V2 opt-in only** — rejected: unlike ADR-0033's `hybrid_rrf` (which failed its own bar), V2 clears every Part 10 criterion with zero measured regressions on either corpus; there is no evidence-based reason to withhold it.
- **Implement multi-chunk composition / semantic fallback anyway, "to be safe"** — rejected per this task's explicit "implement only if the failure analysis proves it is needed" instruction; n=1 and n=0 respectively do not meet that bar.

## Tradeoffs

- V2 only partially resolves the weak-anchor conflict false-collision mechanism (10 of 26 original chunking-corpus rejections remain `conflicting_evidence`, largely because a second, unrelated candidate sentence can still coincidentally share 2+ generic keywords with the question). A more aggressive fix (e.g. document/section-family scoping) was not attempted here — it would move further from "prefer structural/typed matching over ad-hoc exceptions" and risk new false negatives without its own bake-off evidence; left as a future reconsideration trigger.
- `evaluate_chunk_support_v2` is somewhat more expensive per call (original-case + lowercased text both retained, nearest-value distance computed) — not measured as latency-significant here (both bake-off arms' p50/p95 were effectively identical) but not formally load-tested.

## Consequences

- `settings.EVIDENCE_VERIFIER_VERSION` default is now `"v2"`; rollback (if ever needed) is the same one-line config change ADR-0031/0032/0033 established as this project's pattern — no code change required.
- `EvidenceSufficiencyV1Verifier` remains fully intact and selectable (`EVIDENCE_VERIFIER_VERSION=v1`), including in the evaluation engine (`EvaluationRunOptions.evidence_verifier_override`) and `RAGOrchestratorDependencies.evidence_verifier`, mirroring the existing reranker/query-transformer override pattern exactly.
- New Prometheus metrics (`evidence_verifier_outcomes_total`, `evidence_verifier_latency_ms` — `app.observability.otel_metrics.record_evidence_verifier_outcome`) let this promotion's real-traffic effect be monitored the same way ADR-0031-0033's promotions are.

## Future reconsideration triggers

- A structural fix for the remaining weak-anchor conflict false positives (10 still-failing cases) — likely requires document/section-family scoping rather than a keyword-count threshold, and its own bake-off.
- The `chunking_dataset.json` `similar_but_absent` category's 0% pass rate under `mode="mock"` evaluation — appears unrelated to evidence sufficiency (identical both arms) and worth its own investigation, out of this task's scope.
- Real customer traffic volume sufficient to evaluate `grounding.py` in shadow mode against V2 specifically (`docs/future/GuardrailsV2.md`'s still-open question).
- If a future corpus/case proves multi-chunk composition or a semantic fallback is genuinely needed (more than the n=1/n=0 seen here), implement it then, bounded as Part 3/Part 6 of this task's specification describe.
