# Evaluation Framework Architecture

**Never change evaluation thresholds, scoring weights, or gate policy without explicit instruction** — see `CLAUDE.md`. This document describes the current framework only.

## What it does

Runs a dataset of real assistant questions through the actual `RAGOrchestrator` (`retrieval.md`) — the same code path production traffic uses, never a reimplementation — and scores retrieval quality and answer quality deterministically, with optional LLM-judge grading for nuance.

## Data model

`app.db.models.evaluation`: `EvaluationDataset` → `EvaluationCase` (question, expected documents/sources, expected answerability, category, tags) → `EvaluationRun` (one execution of a dataset against one assistant: provider/model/prompt versions, mode `mock`/`live`, policy snapshot, status, case counters) → `EvaluationResult` (per run×case: actual answer, retrieval/answer metrics, judge scores, `passed`, `hard_failure`, failure reasons). `run_id`/`case_id` are first-class DB primary keys, already the trace-tagging model that `observability.md`'s `eval_run_id`/`eval_case_id` reuses.

## Execution engine

`app.evaluation.engine.run_evaluation()`: for each case, builds a `RAGOrchestrationRequest` and calls `RAGOrchestrator.answer()` inside a **`shadow_rag_session()`** (`app.evaluation.shadow_session`) — a rolled-back-at-the-end session so `ChatSession`/`ChatMessage`/`Citation` rows the orchestrator writes never actually commit; only the `EvaluationRun`/`EvaluationResult` rows (written through the caller's real session) persist. Cases run via a `ThreadPoolExecutor` (`max_workers=1`) with a per-case timeout, specifically so a hung/slow provider call can't hang the whole run.

**Important**: this thread-pool execution model means Python `contextvars` do not propagate into the case-execution thread — anything that needs to be tagged per-case (like AI trace context) must be passed explicitly as a parameter, never assumed to be ambient. See `observability.md`'s "Limitations" section for a concrete instance of this (AI trace recording is disabled for evaluation runs on SQLite specifically, due to a real cross-thread contention issue).

## Scoring and gating

- `app.evaluation.metrics.{answer,retrieval,aggregate}` — deterministic metric computation.
- `app.evaluation.scoring.score_case()` — pass/fail + hard-failure determination per case.
- `app.evaluation.policy.EvaluationPolicy` / `load_policy_from_env()` — the actual thresholds (max p95 latency, etc.) — **this is the file that must not be changed without explicit instruction**.
- `app.evaluation.gate.evaluate_gate()` — run-level pass/fail against the policy, used as a launch-readiness gate.
- `app.evaluation.graders/` — optional LLM-judge grading (via Ollama), calibration, rubrics, caching.

## Real vs. mock embeddings

`--real` mode (`app.evaluation.embedding_config`) uses a real embedding provider (must exactly match whatever provider/model/dimension the target dataset's chunks were seeded with — retrieval filters by exact match, see `vector-storage.md`) instead of the deterministic mock. `recommended_min_similarity_score()` applies an evidence-based threshold for real-embedding runs so they're launch-representative by default.

## CLI operations

`app.operations.eval_{golden_setup,run,grade,compare,report,score_distribution}.py` — one script per operation, invoked via `python -m app.operations.eval_run ...` etc. See each script's own module docstring for exact flags before using it.

## Production feedback loop

Production failures become golden `EvaluationCase` rows through a human-gated pipeline, not automatically. `app.evaluation.feedback.detector.scan_for_candidates()` scans `ChatMessage`/`AITrace`/`AIGuardrailTrace`/`AIModelCallTrace` for failure signals and creates/bumps `EvaluationCandidate` rows (`app.db.models.evaluation_candidate`) via `app.repositories.evaluation_candidate_repository`, always redacting question/response text first (`app.observability.redaction.redact_free_text`). A reviewer triages each candidate (`app/api/v1/evaluation_candidates.py`, dashboard at `/feedback-loop`) and only an explicitly `accepted` candidate can be `promote_candidate()`'d into a new `EvaluationCase`, which bumps `EvaluationDataset.version` and writes an `EvaluationDatasetVersionEvent` changelog row — existing `EvaluationRun`/`EvaluationResult` rows are never mutated. `app.evaluation.production_gate.evaluate_production_readiness()` is the release-blocking counterpart to `evaluate_gate()` above, checking accepted-but-still-failing cases, stale baselines, and missing regression evidence. Full detail: `docs/04_Engineering/Evaluation_Production_Feedback_Loop.md`, `docs/04_Engineering/Candidate_Triage_Guide.md`, `docs/04_Engineering/Dataset_Promotion_Policy.md`, `docs/06_Operations/Nightly_Evaluation_VPS_Guide.md`, `docs/06_Operations/Regression_Release_Policy.md`.

## Terminology rule

Never label a metric "hallucination rate" unless confirmed through human review — use "unsupported-answer signal," "grounding failure," "evidence-insufficient response," or "review-confirmed incorrect answer" as appropriate. See `docs/03_AI/AI_Metrics_Dictionary.md`.

## Rules

- Changing `app.evaluation.policy` or `app.evaluation.gate` thresholds requires explicit instruction — these encode a previously-agreed quality bar.
- New evaluation categories/cases are additive; do not remove existing golden-dataset cases without instruction.
- Always run `npm run eval:test` after touching anything in `app/evaluation/*` or `app/ai/rag_orchestrator.py`.

## Evaluation-gated prompt promotion

`app.evaluation.prompt_promotion_gate.evaluate_prompt_candidate()` (`docs/04_Engineering/Prompt_Evaluation_and_Promotion_Policy.md`) reuses this exact engine to gate a candidate `PromptVersion` before approval/deployment — it calls the unmodified `run_evaluation()`/`evaluate_gate()`, with `EvaluationRunOptions.prompt_version_override_id` forcing every case to resolve one specific candidate. `EvaluationRun.prompt_version_id` (a new nullable FK) distinguishes a prompt-gate run from an ordinary dataset-quality run.
