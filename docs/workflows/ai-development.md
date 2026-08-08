# AI Development Lifecycle

How each AI subsystem moves from research to production, and back into improvement. Each subsystem below follows the same 10-phase shape: Research → Prototype → Offline Evaluation → Golden Dataset → Regression Testing → Observability → Shadow Deployment → Production Rollout → Production Evaluation → Improvement Loop. This is a specialization of `docs/workflows/engineering-lifecycle.md` for AI-specific work — use that document's stages 9-14 (Evaluation through Observability) as the detailed reference for what "Offline Evaluation," "Regression Testing," and "Observability" mean concretely.

## Embedding Models

1. **Research**: candidate providers/models compared on paper (dimension, cost, licensing) — see `docs/future/EmbeddingBakeoff.md`.
2. **Prototype**: embed a small sample corpus with the candidate, no production wiring.
3. **Offline Evaluation**: run the standard evaluation case set's retrieval-quality metrics against the candidate.
4. **Golden Dataset**: verify the existing case set has enough variety to detect a real quality difference; add cases if not.
5. **Regression Testing**: compare recall/precision against the current production embedding model, not just against zero.
6. **Observability**: confirm `ai_model_call_traces`/cost fields would populate correctly for the new provider (`docs/architecture/observability.md`).
7. **Shadow Deployment**: dual-write embeddings (new provider alongside current) without serving from the new one — see `docs/future/QdrantMigration.md`'s dual-write pattern as the template.
8. **Production Rollout**: cut over per-workspace or globally only after shadow comparison shows parity or improvement.
9. **Production Evaluation**: monitor retrieval quality signals in production traces post-rollout.
10. **Improvement Loop**: findings feed `docs/future/EmbeddingBakeoff.md`'s next iteration or the next model generation's evaluation.

## Generation Models

1. **Research**: candidate providers/models compared on capability, cost, latency, data-handling terms.
2. **Prototype**: wire the candidate behind `AIProvider` (`docs/architecture/retrieval.md`) in a non-production environment.
3. **Offline Evaluation**: full evaluation-gate run (deterministic + advisory grader dimensions, `docs/engineering/graders.md`) against the candidate.
4. **Golden Dataset**: verify case coverage for the specific behaviors this model needs to get right (grounding, citation discipline, refusal behavior).
5. **Regression Testing**: compare against the current production model on the same case set, not in isolation.
6. **Observability**: confirm cost/token accounting fields are correctly populated (`cost_calc_version`, never silently `$0` for unknown pricing).
7. **Shadow Deployment**: run the candidate against real (redacted) production query samples without serving its output, per `docs/future/PromptOptimisation.md`'s shadow-testing pattern.
8. **Production Rollout**: gradual rollout (`docs/future/ModelRouting.md` once routing exists; single-provider swap otherwise), monitored closely.
9. **Production Evaluation**: continuous evaluation sampling (`docs/future/EvaluationV2.md`) once available; manual trace review until then.
10. **Improvement Loop**: production findings inform the next model research cycle and update the golden dataset.

## Prompt Templates

1. **Research**: identify the specific failure mode or improvement opportunity a new prompt version should address.
2. **Prototype**: draft the new version in `draft` status (ADR 0003's lifecycle) — no production traffic sees it.
3. **Offline Evaluation**: run the full evaluation case set against the `draft`/`testing` version.
4. **Golden Dataset**: ensure cases exist for the specific behavior being changed.
5. **Regression Testing**: compare against the current `active` version on the same case set — no regression on gating dimensions.
6. **Observability**: confirm `prompt_key`/`prompt_version`/`prompt_hash` will be recorded correctly for the new version.
7. **Shadow Deployment**: shadow-test against production traffic samples per `docs/future/PromptOptimisation.md`.
8. **Production Rollout**: promote `testing → active` only once promotion criteria are met; old version moves to `deprecated`, never edited in place.
9. **Production Evaluation**: monitor grader scores and fallback rate post-promotion.
10. **Improvement Loop**: regressions or new failure patterns start the next prompt version's Research phase.

## Retrieval

1. **Research**: identify a specific retrieval-quality gap from observability data (`ai_retrieval_traces`) — e.g. exact-term misses, low-similarity selections.
2. **Prototype**: implement the candidate change (chunking parameter, hybrid search, reranking — see `docs/future/RetrievalOptimisation.md`, `docs/future/HybridRetrieval.md`, `docs/future/Reranking.md`) behind a flag.
3. **Offline Evaluation**: precision/recall comparison on the evaluation case set.
4. **Golden Dataset**: add cases targeting the specific gap identified in Research.
5. **Regression Testing**: verify no regression on cases the current retrieval already handles well.
6. **Observability**: confirm new retrieval traces populate `ai_retrieval_traces` correctly with the new ranking/source data.
7. **Shadow Deployment**: compute both old and new ranking, serve old, log divergence.
8. **Production Rollout**: per-workspace flag rollout, monitored via observability.
9. **Production Evaluation**: track fallback/evidence-insufficient rate post-rollout.
10. **Improvement Loop**: findings feed the next retrieval-optimisation cycle, per `docs/engineering/implementation-order.md`'s retrieval-quality track sequencing.

## Memory

1. **Research**: define the specific conversational gap short-term memory would close (see `docs/future/MemoryV2.md`).
2. **Prototype**: inject recent-turn context into `prompt_assembly` behind a flag, non-production.
3. **Offline Evaluation**: multi-turn evaluation case set (does not exist yet — must be built as part of this work).
4. **Golden Dataset**: build the multi-turn case set referenced above.
5. **Regression Testing**: verify single-turn question quality is unaffected.
6. **Observability**: confirm memory-context-injection is traceable (what context was injected, per request).
7. **Shadow Deployment**: compute with-memory and without-memory answers, serve without, compare.
8. **Production Rollout**: gradual, flag-gated, with explicit privacy review before any rollout (`docs/future/MemoryV2.md`).
9. **Production Evaluation**: monitor multi-turn conversation coherence signals.
10. **Improvement Loop**: findings inform long-term memory design (`docs/future/MemoryV2.md`'s later phase).

## Evaluation (the framework itself)

1. **Research**: identify a gap in what's currently measured (a failure mode with no corresponding case or metric).
2. **Prototype**: draft new evaluation cases or a new scoring dimension.
3. **Offline Evaluation**: not applicable in the usual sense — validate the new cases/dimension against known-good and known-bad examples.
4. **Golden Dataset**: the change to the golden dataset *is* the deliverable here.
5. **Regression Testing**: verify existing passing cases still pass under any scoring-logic change.
6. **Observability**: confirm evaluation run results remain queryable/traceable as before.
7. **Shadow Deployment**: run new scoring logic alongside old, compare verdicts before switching.
8. **Production Rollout**: new cases/dimensions become part of the standard gate; threshold changes require explicit instruction (`CLAUDE.md`).
9. **Production Evaluation**: not applicable — this stage is about evaluating other things.
10. **Improvement Loop**: `docs/future/EvaluationV2.md`'s continuous-evaluation loop is the long-term version of this.

## Guardrails

1. **Research**: identify a failure mode not caught by layers A-H, typically from observability/incident data.
2. **Prototype**: implement the candidate layer in shadow mode (compute verdict, don't act on it) — see `docs/future/GuardrailsV2.md`.
3. **Offline Evaluation**: measure what the candidate layer would have caught against the evaluation case set and historical traces.
4. **Golden Dataset**: add cases specifically exercising the new failure mode.
5. **Regression Testing**: verify the new layer doesn't false-positive against known-good cases.
6. **Observability**: confirm the new layer emits `ai_guardrail_traces` rows following the existing pattern.
7. **Shadow Deployment**: run in shadow mode against real production traffic before acting on its verdict.
8. **Production Rollout**: wire in live only once shadow-mode data justifies it (`docs/future/GuardrailsV2.md`'s process).
9. **Production Evaluation**: monitor the new layer's trigger rate and any downstream fallback-rate change.
10. **Improvement Loop**: false positives/negatives found in production refine the layer's logic, looping back to Prototype.

## Graders

1. **Research**: identify an answer-quality dimension not yet covered by existing rubric dimensions.
2. **Prototype**: draft the new `GraderDimension` and its rubric/prompt.
3. **Offline Evaluation**: run the new dimension against `fixtures/calibration_set.json`.
4. **Golden Dataset**: extend the calibration set if it doesn't cover the new dimension's failure modes.
5. **Regression Testing**: verify existing dimensions' scores are unaffected by the new dimension's addition.
6. **Observability**: confirm the new dimension's results are captured in evaluation run results and (if relevant) traces.
7. **Shadow Deployment**: run the new dimension as advisory-only (it already is, by default — ADR 0025) before considering gating.
8. **Production Rollout**: the dimension ships as advisory; promotion to gating is a separate, later decision (`docs/future/EvaluationV2.md`).
9. **Production Evaluation**: track calibration agreement across releases per `docs/engineering/graders.md`.
10. **Improvement Loop**: sustained calibration agreement triggers the promotion conversation; poor agreement sends the dimension back to Prototype.

## Observability (the system itself)

1. **Research**: identify a gap in what's currently traced/measured (a production question that can't be answered from existing traces).
2. **Prototype**: add the new trace field/stage/table in a non-production environment.
3. **Offline Evaluation**: verify the new signal is captured correctly for known test scenarios.
4. **Golden Dataset**: not directly applicable — closest equivalent is a set of known trace scenarios to verify against.
5. **Regression Testing**: verify existing trace consumers (API, UI, alerts) still work with the new/changed schema.
6. **Observability**: (self-referential) — confirm the new instrumentation itself doesn't add unacceptable latency or failure risk (fail-safe no-op pattern, `docs/architecture/observability.md`).
7. **Shadow Deployment**: add the new field/table as purely additive first; don't remove or repurpose existing fields.
8. **Production Rollout**: ship as additive; migration follows the dialect-safe pattern (`docs/architecture/observability.md`).
9. **Production Evaluation**: confirm the new signal actually gets used (dashboard, alert, or investigation) — an unused trace field is a maintenance cost with no benefit.
10. **Improvement Loop**: `docs/operations/observability-workflow.md` and `docs/operations/continuous-improvement.md` describe how this feeds back continuously.

## Cross-subsystem rule

No subsystem above skips Offline Evaluation or Regression Testing before Production Rollout, regardless of how small the change feels — this is the direct application of `docs/principles/engineering-principles.md`'s evaluation-first and no-regression-acceptance principles to AI-specific work.
