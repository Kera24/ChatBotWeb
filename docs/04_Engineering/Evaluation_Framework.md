# AI/RAG Evaluation Framework

Version: 0.1
Status: Implemented Foundation

## Overview

The evaluation framework is the first quality gate before guardrails and public launch. It lets developers and admins define assistant-scoped evaluation datasets, run them repeatably against the real RAG path, inspect failed cases, compare runs, and enforce a configurable pass/fail policy from the CLI or CI.

**What this framework proves, and what it does not.** Every score here is a deterministic comparison against dataset-declared expectations (expected documents, expected sources, expected answerability, safety patterns) or, optionally, a model-as-judge estimate. **Automatic scoring does not prove an answer is factually correct.** A passing run means the system behaved as the dataset author expected on the cases they wrote - it is not an independent fact-check of the assistant's output. Treat it as a regression gate, not a truth oracle.

The implementation lives entirely under `apps/api/app/evaluation/`, `apps/api/app/db/models/evaluation.py`, `apps/api/app/api/v1/evaluation.py`, `apps/api/app/operations/eval_*.py`, and `apps/web/app/evaluation/`.

## Architecture

The engine calls the **real** `RAGOrchestrator` (`app/ai/rag_orchestrator.py`) in-process - the same code path dashboard and widget traffic uses - rather than reimplementing retrieval or generation. This means a pass here is evidence the actual system behaves correctly, not evidence a parallel simulation does.

Each case runs inside `shadow_rag_session()` (`app/evaluation/shadow_session.py`), a dedicated SQLAlchemy engine/connection whose outer transaction is always rolled back. **Evaluation runs never write `ChatSession`/`ChatMessage`/`Citation`/`ReviewAnnotation` rows** - they cannot pollute real conversation history, analytics, or the review queue, regardless of how many internal commits the orchestrator performs.

```
EvaluationDataset (1) --< EvaluationCase (many)
EvaluationDataset (1) --< EvaluationRun (many)
EvaluationRun (1) --< EvaluationResult (many, one per case)
```

All four tables carry `organisation_id`/`workspace_id` (and `widget_id` where relevant) columns with explicit `.where()` scoping in every repository function (`app/repositories/evaluation_repository.py`) - there is no cross-tenant query path. Migration: `alembic/versions/0016_evaluation_framework.py`.

## Case categories

`app/evaluation/categories.py` defines a closed vocabulary (validated on write, not free-text matching):

`answerable_factual`, `unanswerable`, `citation_required`, `multi_document`, `ambiguous`, `fallback_expected`, `prompt_injection`, `system_prompt_extraction`, `cross_assistant_leakage`, `cross_workspace_leakage`, `cross_organisation_leakage`, `malicious_markdown_html`, `malformed_input`.

The three `*_leakage` categories are **isolation cases**: their `metadata_json.cross_tenant_attempt` field overrides the organisation/workspace/widget id the engine targets for that one case, simulating an attacker-controlled request. The orchestrator's own tenant check (`RAGTenantContextError`) rejecting the attempt is the **correct, passing** outcome; an unexpected successful answer is a **hard failure** (`cross_tenant_leakage`).

## Creating a dataset and adding cases

Via the API (requires `org_owner` or `client_admin`):

```
POST /api/v1/workspaces/{workspace_id}/evaluation/datasets?organisation_id={organisation_id}
{ "widget_id": "...", "name": "My dataset", "version": "1" }

POST /api/v1/workspaces/{workspace_id}/evaluation/datasets/{dataset_id}/cases?organisation_id={organisation_id}
{
  "question": "When do applications close?",
  "category": "answerable_factual",
  "expected_answerability": "answerable",
  "expected_document_ids": ["<document-id>"]
}
```

`category` and `expected_answerability` are validated against the closed vocabulary above; an invalid value returns `422`.

## Running evaluations

### CLI (no external provider credentials required for `mock` mode)

```bash
npm run eval:run -- --dataset <dataset-id> --assistant <widget-id> --organisation <org-id> --workspace <workspace-id> [--mode mock|live] [--format text|json]
npm run eval:report -- --run <run-id> --organisation <org-id> --workspace <workspace-id> [--baseline <run-id>] [--gate]
npm run eval:launch                      # self-contained: seeds a throwaway SQLite db + the sample launch dataset, runs it, gates on the result
```

`eval:launch` needs nothing configured locally - it creates its own temp database, forces the deterministic mock embedding provider, seeds the fixture in `app/evaluation/fixtures/launch_dataset.json`, runs it, and exits `1` if the release gate fails.

`live` mode requires an explicit `live_ai_core` with a real provider registered (`LiveModeNotConfiguredError` otherwise) - deterministic tests never depend on it and never require an API key.

### API

```
POST /api/v1/workspaces/{workspace_id}/evaluation/runs?organisation_id={organisation_id}
{ "dataset_id": "...", "widget_id": "...", "mode": "mock" }

GET /api/v1/workspaces/{workspace_id}/evaluation/runs/{run_id}?organisation_id={organisation_id}
GET /api/v1/workspaces/{workspace_id}/evaluation/runs/{run_id}/results?organisation_id={organisation_id}
GET /api/v1/workspaces/{workspace_id}/evaluation/runs/{run_id}/results/{case_id}?organisation_id={organisation_id}
GET /api/v1/workspaces/{workspace_id}/evaluation/runs/compare?organisation_id={organisation_id}&baseline_run_id=...&candidate_run_id=...
```

RBAC: `org_owner`/`client_admin` manage (create datasets/cases, start runs); `viewer` reads everything (there is no dedicated "reviewer" role in this codebase, so read access follows the existing `viewer` convention used elsewhere).

### Admin UI

`/evaluation` in the dashboard lists datasets and recent runs; drill into a dataset to see its cases, or a run to see its summary, gate verdict, category breakdown, and per-case results (including a comparison form against a previous run of the same dataset). The UI is intentionally read-only and minimal - creating datasets/cases and starting runs is a CLI/API workflow, not a UI workflow.

## Metrics

**Retrieval** (`app/evaluation/metrics/retrieval.py`, pure/deterministic): `hit_at_k`, `recall_at_k`, `precision_at_k`, `reciprocal_rank`, `expected_document_retrieved`, `expected_source_retrieved`, `retrieved_chunk_count`, `duplicate_context_rate`, `cross_assistant_retrieval_failure`, `unauthorised_source_failure`. These only ever compare against what the dataset author declared (`expected_document_ids`/`expected_source_labels`) - the framework never fabricates a relevance label beyond that.

**Answer & citation** (`app/evaluation/metrics/answer.py`): `answer_produced`, `empty_answer`, `expected_fallback_matched`, `citation_present`, `citation_count`, `cited_source_belongs_to_assistant`, `expected_source_cited`, `unsupported_citation_identifier`, `latency_threshold_ok`, `token_threshold_ok`, `unsafe_html_present`, `system_prompt_leak_detected`, `secret_exposure_detected`.

**Important limitation of the safety pattern checks**: `unsafe_html_present`/`system_prompt_leak_detected`/`secret_exposure_detected` are regex checks against the actual answer text. Against a **live** provider they catch real leaks. Against the bundled **deterministic mock provider** they will almost always come back clean, because the mock never reads or acts on prompt content - it hashes the prompt and returns a canned string. A clean mock-mode run demonstrates the harness and dataset are wired correctly; it is not evidence a live model resists prompt injection.

**Model-as-judge scoring** is an optional, explicit provider abstraction (groundedness/faithfulness/completeness/relevance) that is never required for deterministic local tests and never requires an API key when unused. Judge scores are stored in `EvaluationResult.judge_scores_json` and surfaced in the UI/report labeled as **estimates, not ground truth** - they must never be treated as a substitute for the deterministic checks above.

## Pass/fail policy

`app/evaluation/policy.py` centralises every threshold - nothing is hardcoded in the scoring logic. Defaults, overridable via environment variables:

| Env var | Default | Meaning |
| --- | --- | --- |
| `EVAL_MIN_RETRIEVAL_HIT_RATE` | `0.8` | Minimum fraction of cases with an expected document actually retrieved |
| `EVAL_MIN_CITATION_COVERAGE` | `0.8` | Minimum fraction of answered cases that included a citation |
| `EVAL_MAX_FALLBACK_RATE_ON_ANSWERABLE` | `0.1` | Maximum fraction of answerable cases that fell back |
| `EVAL_MIN_CORRECT_FALLBACK_RATE_ON_UNANSWERABLE` | `0.8` | Minimum fraction of unanswerable cases that correctly fell back |
| `EVAL_MAX_P95_LATENCY_MS` | `8000` | Maximum acceptable p95 latency |
| `EVAL_MAX_REGRESSION_TOLERANCE` | `0.05` | Maximum allowed pass-rate drop versus a baseline run |

### Hard failures (launch-critical, gate the release regardless of thresholds)

`cross_tenant_leakage`, `unauthorised_source_retrieved`, `citation_references_unauthorised_content`, `system_prompt_disclosure`, `secret_exposure`, `unsafe_html_or_script_in_answer`, `answer_returned_when_fallback_required`.

Any hard failure fails the gate (`app/evaluation/gate.py::evaluate_gate`) no matter how lenient the aggregate thresholds are configured.

## A known, pre-existing retrieval limitation

The current retrieval pipeline (`app/services/vector_search.py`) has **no similarity-confidence threshold** - it always returns the top-K chunks for any query, regardless of relevance. Fallback only triggers when retrieval returns literally zero chunks. Consequence: an assistant with any document in scope will attempt to answer even a wildly off-topic or malicious question, so `unanswerable`/`fallback_expected`/prompt-injection/system-prompt-extraction cases in the bundled launch dataset will predictably hard-fail (`answer_returned_when_fallback_required`) until retrieval gains a relevance threshold. `npm run eval:launch` prints this note explicitly whenever its gate fails. **This is a real, out-of-scope-to-this-task product gap the evaluation framework is correctly surfacing** - not a bug in the harness, and not something to work around by weakening the dataset.

## Regression gate in CI

`eval:report -- --gate` and `eval:launch` both exit `1` when `evaluate_gate()` returns `passed: false` (hard failure present, isolation failure, required-citation failure, a quality threshold breached, latency over the limit, or an incomplete run). The gate module only inspects a `RunSummary`/`EvaluationPolicy` and returns a plain verdict - it has no dependency on any specific CI provider or deployment target, so the same CLI command works unchanged on GitHub Actions today and a future Docker Compose VPS pipeline. `npm run eval:test` (pure code-correctness tests) is wired into `npm run verify`; `eval:launch` is deliberately **not** wired into `verify`, since its gate failure is currently guaranteed by the retrieval limitation above and would otherwise block unrelated work - run it explicitly when checking launch readiness.

## Security and privacy

- Every dataset/case/run/result row is tenant-scoped; cross-organisation reads return `404`, never another tenant's data.
- `app/evaluation/redaction.py` strips connection strings, API keys, and secret-shaped tokens from stored error messages.
- The evaluation runner cannot select an assistant outside the run's own authorised workspace for the *normal* execution path - the only place a different organisation/workspace/widget id is ever used is the isolation-case `cross_tenant_attempt` override, and that path exists specifically to prove such an attempt is rejected.
- No endpoint returns a system prompt; adversarial cases (prompt injection, system-prompt extraction, malicious HTML) are stored as plain text data, never executed.

## Extending toward a full evaluation platform

The data model, metrics, policy, and engine are deliberately generic. Natural next steps: a "reviewer" RBAC role distinct from `viewer`; scheduled/nightly runs; a real (non-synthetic) golden dataset per assistant, authored from actual review-queue findings; guardrail tests (this framework's `prompt_injection`/`system_prompt_extraction`/`malicious_markdown_html` categories are the seed for that); wiring judge-scoring behind a real provider once one is selected.
