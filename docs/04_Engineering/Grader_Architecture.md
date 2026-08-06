# Grader Architecture

Optional, offline, LLM-based grading layer for semantic answer quality,
complementing (never replacing) the deterministic evaluation/guardrail
pipeline built in the prior cycles. See
[Grader_Rubrics.md](./Grader_Rubrics.md) for the rubric specification,
[Evaluation_Framework.md](./Evaluation_Framework.md) and
[Guardrails_Task_Specification.md](./Guardrails_Task_Specification.md) for
the deterministic system this layer sits alongside.

## Architecture

```
app/evaluation/graders/
  rubrics.py       - version-controlled dimension definitions (RUBRIC_VERSION)
  contracts.py      - pydantic GraderResult / PairwiseVerdict / ConsistencyReport (strict validation)
  context.py         - GradingContext / EvidenceItem (sanitised, assistant-scoped grader input)
  provider.py        - GraderProvider ABC + MockGraderProvider (deterministic, dependency-free)
  ollama_provider.py - OllamaGraderProvider (local model via Ollama /api/generate, format=json)
  config.py           - EVAL_GRADER_* env loading, build_real_eval_grader_provider() (fails clearly, no silent fallback)
  prompts.py          - versioned grading/pairwise prompts (GRADER_PROMPT_VERSION)
  claims.py            - deterministic claim splitting + numeric/currency/date/duration support check
  cache.py              - in-process cache keyed by hash(answer, evidence, rubric, model)
  engine.py              - orchestration: build context, grade, measure consistency, persist, pairwise+swap
  calibration.py          - runs graders against the human calibration set, reports agreement/threshold
  grading_report.py        - dimension averages/pass rates/distributions/disagreement report

app/operations/eval_grade.py    - CLI: grade a run (or --calibrate)
app/operations/eval_compare.py  - CLI: baseline vs candidate, deterministic always + optional --grader
app/evaluation/fixtures/calibration_set.json - 10 hand-labelled examples
```

**Never on the live request path.** Nothing in `app/evaluation/graders/` is
imported by `app/ai/rag_orchestrator.py`. Grading is a separate, offline CLI
step run against already-persisted `EvaluationResult` rows - no grader runs
automatically as part of an evaluation run, and never on a production
request.

## Provider setup

`EVAL_GRADER_PROVIDER` (default `mock`), `EVAL_GRADER_MODEL`,
`EVAL_GRADER_BASE_URL` (default `http://localhost:11434`),
`EVAL_GRADER_TEMPERATURE` (default `0.0` - deterministic where supported),
`EVAL_GRADER_MAX_TOKENS` (default `512`), `EVAL_GRADER_TIMEOUT_SECONDS`
(default `60`). Mirrors `EVAL_EMBEDDING_*`'s exact pattern
(`app/evaluation/embedding_config.py`).

`build_real_eval_grader_provider()` **fails clearly** (raises
`GraderNotConfiguredError`) rather than silently returning the mock provider
when `EVAL_GRADER_PROVIDER` is unset/`mock`, when `ollama` is requested
without `EVAL_GRADER_MODEL`, or when the requested Ollama model is not
actually installed (`check_ollama_grader_model_available` preflight, mirrors
`check_ollama_embedding_model_available`). No API credentials are hardcoded
anywhere in this subsystem.

### Local Ollama grader setup

```
ollama pull <a chat-capable model, e.g. qwen3.5>
$env:EVAL_GRADER_PROVIDER = "ollama"
$env:EVAL_GRADER_MODEL = "qwen3.5"
npm run eval:grade -- --run <run-id> --organisation <id> --workspace <id>
```

The Ollama provider calls `/api/generate` with `format: "json"` (Ollama's
native structured-output mode) and validates the response against the
`GraderResult`/`PairwiseVerdict` pydantic contracts - malformed output raises
`GraderOutputValidationError`, caught per-dimension by the engine and
recorded as an `{"error": ...}` entry, never crashing the whole grading run
or silently guessing a score.

## Structured output format

Every grader call returns a `GraderResult`:
```json
{
  "dimension": "groundedness", "score": 0.8, "passed": true, "confidence": 0.7,
  "reason": "...", "unsupported_claims": [], "supported_claims": [...],
  "citation_findings": [], "rubric_version": "v1", "prompt_version": "v1",
  "grader_provider": "ollama", "grader_model": "qwen3.5",
  "is_model_generated_estimate": true, "graded_at": "..."
}
```
`is_model_generated_estimate` is always `true` and is part of the pydantic
schema itself (not just documentation) - every persisted and reported score
carries this flag so it can never be mistaken for ground truth downstream.

## Calibration methodology

`app/evaluation/fixtures/calibration_set.json` - 10 synthetic, hand-labelled
examples (built from the same fictional Northwind corpus as
`golden_dataset.json`, no customer data) covering: excellent answer,
partially complete, unsupported/hallucinated, correct fallback, unnecessary
fallback, good/poor clarification, valid citation support, citation present
but unsupported, concise vs. verbose. Each has a `human_label` (`passed` +
`score_band`) and `reviewer_notes`.

`npm run eval:grade:calibrate` runs the configured grader against every
example and reports, per dimension: agreement rate with the human label,
false positives, false negatives, score bias (mean grader score vs. the
human score band's midpoint), and whether the dimension clears
`_CALIBRATION_PASS_AGREEMENT_THRESHOLD = 0.8` (`calibration.py`).

## Consistency requirements

`--repetitions N` repeats each grading call N times and reports
`agreement_rate` (fraction of repetitions whose `passed` matches the
majority) and `score_variance`. A dimension with `score_variance >
_CONSISTENCY_VARIANCE_THRESHOLD (0.05)` is marked `is_consistent = False`
and must not be treated as a stable signal for that run - consistency is
reported per grading run, not hardcoded, since it depends on the actual
model/temperature configured. Position bias for pairwise comparisons is
checked via `compare_pairwise_with_swap_check` (runs the comparison twice,
swapping which answer is presented first, and reports whether the verdict
is consistent after accounting for the swap).

## Advisory vs gating policy

**No dimension is gating today.** `rubrics.py`'s `RubricDefinition.gating`
is `False` for all nine dimensions (asserted by
`tests/test_graders.py::test_no_dimension_is_gating_at_introduction`).
Per the task brief: deterministic hard failures
(`app/evaluation/scoring.py`, `app/evaluation/gate.py`) remain the sole
launch gate; a grader can never override a deterministic safety failure or
mark an unauthorised citation acceptable - there is no code path where a
grader result feeds into `evaluate_gate()` at all.

`groundedness`, `citation_support`, and `fallback_appropriateness` are
explicitly named as *candidates* to become gating once calibration meets
the 0.8 agreement threshold **and** a human maintainer explicitly approves
the change in `rubrics.py` (a code change, not a config flag) - this has not
happened. `relevance`/`clarity`/`directness` remain advisory unless
explicitly approved, per the task brief.

## Human-review workflow

A grading report (`eval_grade.py`/`grading_report.py`) surfaces: per-
dimension averages and pass rates, score distributions, low-confidence
findings (`confidence < 0.3`) flagged for human review, and a
deterministic-vs-grader disagreement list (cases the deterministic gate
marked a hard failure but a grader nonetheless passed) - always framed as
"deterministic gate remains authoritative," never as a correction to it.
Human reviewers are expected to spot-check disagreements and low-confidence
findings, not to trust grader scores at face value.

## Cost and latency

`GradingRunStats` (`engine.py`) tracks `total_calls`, `errors`,
`total_latency_ms` per run; `GraderResultCache.stats()` tracks
`hits`/`misses`/`entries`. `--failed-only` and `--dimension` restrict
grading to a subset (Section 13's "grading only changed/failed cases").
Caching is keyed by `hash(dimension, rubric_version, grader_model, question,
answer, answer_state, evidence)` so an unchanged case is never re-graded
within the same process. `EVAL_GRADER_TIMEOUT_SECONDS` bounds each call;
timeouts and provider errors are caught per-dimension (not per-run) and
recorded as an error entry rather than aborting the whole grading pass. No
per-provider token-cost pricing table exists yet (Ollama is local/free) -
`total_tokens`-based cost estimation is a documented future extension once
an external paid provider is configured.

## Production feedback use (documented, not implemented)

Graders may later assist production triage: scoring thumbs-down responses,
prioritising the review queue, flagging likely-unsupported claims for
reviewer attention, suggesting golden-dataset additions from recurring
failure patterns, and comparing candidate fixes before a prompt/retrieval
change ships. **Graders must never automatically change a production answer
or the knowledge base** - human review remains authoritative for production
failure intake. None of this is wired up yet; it is a documented direction
for a future phase, consistent with "no grader runs automatically on every
production request at launch."

## Known limitations

- The `MockGraderProvider` uses simple, deterministic lexical-overlap
  heuristics, not a real model - useful for testing the pipeline end to end
  and for calibration-mechanism validation, but its own calibration
  agreement is intentionally imperfect (50% on `fallback_appropriateness`/
  `clarification_quality` in this project's calibration run - see below),
  which is the calibration mechanism correctly identifying a weak grader
  rather than rubber-stamping it.
- Claim extraction (`claims.py`) is a deterministic sentence-splitter, not
  true claim decomposition - a citation marker's scope within a sentence is
  ambiguous, and one sentence is not always exactly one factual claim
  (explicitly disclaimed, matching the task brief's own instruction).
- The deterministic numeric/currency/date/duration support check
  (`deterministic_value_support`) reuses `app.ai.guardrails.evidence_sufficiency`'s
  value extractors and is authoritative when it applies (has checkable
  values); it returns `None` (undetermined) for claims with no checkable
  values, leaving the grader's own judgement as the only signal there.
- No live-Ollama-grader calibration or consistency run is included in this
  task's validation results (see the Validation section) - Ollama's chat
  model (`qwen3.5`) was available in this environment but a live grading
  pass was not run as part of this change; the `mock` provider's run is
  reported instead, with the live-Ollama code path fully built, unit-tested
  for its HTTP/parsing/validation logic, and ready to run via
  `EVAL_GRADER_PROVIDER=ollama`.

## Commands

```
npm run eval:grade -- --run <run-id> --organisation <id> --workspace <id>
npm run eval:grade -- --run <run-id> --organisation <id> --workspace <id> --dimension groundedness
npm run eval:grade -- --run <run-id> --organisation <id> --workspace <id> --failed-only
npm run eval:grade -- --run <run-id> --organisation <id> --workspace <id> --repetitions 3
npm run eval:grade:calibrate
npm run eval:compare -- --baseline <id> --candidate <id> --organisation <id> --workspace <id>
npm run eval:compare -- --baseline <id> --candidate <id> --organisation <id> --workspace <id> --grader
```
All commands are plain `python -m app.operations.X` invocations under the
hood - no shell-specific syntax, so they work unmodified from PowerShell,
Git Bash, or a POSIX shell.
