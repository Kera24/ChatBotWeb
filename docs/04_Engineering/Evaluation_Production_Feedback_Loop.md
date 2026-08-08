# Production Feedback Loop

Version: 2.0
Status: **Implemented.** This document originally specified the design only (v1.0, no runtime collection); the runtime collection, triage workflow, dataset versioning, scheduled evaluation, and regression/release gating described below now exist in code. See "What changed since v1.0" at the end for the delta.
Related: [Evaluation Framework](./Evaluation_Framework.md), [Candidate Triage Guide](./Candidate_Triage_Guide.md), [Dataset Promotion Policy](./Dataset_Promotion_Policy.md), [Golden Dataset Versioning Guide](./Golden_Dataset_Versioning_Guide.md), [Nightly Evaluation VPS Guide](../06_Operations/Nightly_Evaluation_VPS_Guide.md), [Regression Release Policy](../06_Operations/Regression_Release_Policy.md), [Privacy and Redaction Policy](../03_AI/Continuous_Evaluation_Privacy_and_Redaction_Policy.md), [Production Failure Intake Runbook](../06_Operations/Production_Failure_Intake_Runbook.md).

## Purpose

Every production failure an assistant makes is a candidate golden-dataset case. Without a deliberate loop feeding real failures back into the evaluation dataset, the golden dataset only ever tests what its authors already imagined. This is that loop:

```
production request → failure/signal detected → privacy-safe candidate case →
triage → human review → approved golden case → dataset version update →
evaluation run → regression comparison → release decision
```

Every promotion into the golden dataset requires an explicit human "accepted" triage decision — nothing is auto-promoted.

## Signal detection

`app.evaluation.feedback.signals.SignalType` is the full vocabulary. `app.evaluation.feedback.detector.scan_for_candidates()` automatically detects a subset from existing production data (no new instrumentation was added to the RAG request path itself):

| Signal | Source | Automatic? |
|---|---|---|
| `fallback` / `low_confidence` | `ChatMessage.answer_state` | Yes |
| `missing_citation` | Answered `ChatMessage` with zero `Citation` rows | Yes |
| `guardrail_trigger` | `AIGuardrailTrace.blocked` | Yes |
| `provider_failure` | `AIModelCallTrace.outcome != "success"` | Yes |
| `high_latency` | `AITrace.total_latency_ms` > `EvaluationPolicy.max_p95_latency_ms` | Yes |
| `grounding_failure`, `evidence_insufficient` | No production-time grader exists yet | Manual/API only |
| `support_report`, `review_item`, `manual_selection`, `grader_advisory_failure` | Human-initiated | Manual/API only |
| `thumbs_down` | No rating field on `ChatMessage`, no widget feedback UI | **Not implemented** — accepted by the schema/API for forward-compatibility, but nothing produces it yet |

"Do not treat every fallback as a defect" (from the original spec) is implemented as: a non-severe signal type's first sighting creates a candidate at `severity="low"`; it only escalates once it recurs `_RECURRENCE_ESCALATION_THRESHOLD` (3) times. Severe types (`guardrail_trigger`, `provider_failure`) are surfaced at full severity immediately. See `app.repositories.evaluation_candidate_repository.create_or_bump_candidate`.

## Candidate model

`EvaluationCandidate` (`app.db.models.evaluation_candidate`) — organisation/workspace/assistant scoped; `source_trace_id`/`source_conversation_id`/`source_message_id` FKs back to the originating production row (never raw content); `redacted_question`/`redacted_response` always passed through `app.observability.redaction.redact_free_text` before being written, with `redaction_version` recorded; `evidence_refs_json` holds only `{document_id, chunk_id, source_title}` — never quoted chunk content; `triage_status` (`new → triaged/needs_information → accepted/rejected/duplicate → resolved`); `dedup_hash`, `duplicate_of_id`, `occurrence_count`, `is_reopen` for deduplication/recurrence tracking; `promoted_case_id`/`dataset_destination_id` set on promotion.

## Deduplication

`app.evaluation.feedback.dedup` — deterministic only (per spec: "Use deterministic methods... do not auto-merge without review"). `compute_dedup_hash()` hashes a normalized question + assistant + reason code. `find_potential_duplicates()` additionally surfaces token-overlap (Jaccard ≥ 0.6) matches among open candidates as suggestions in the triage UI. **Semantic/embedding-based similarity is not implemented** — a documented gap, not a silent omission; see "What is not yet built" below.

## Triage and promotion

`app/api/v1/evaluation_candidates.py` (RBAC: `org_owner`/`client_admin`/`viewer` read, `org_owner`/`client_admin` write — same shape as `app/api/v1/review.py`) exposes list/detail/create/PATCH-triage/mark-duplicate/promote/metrics endpoints. Dashboard: `/feedback-loop` (queue), `/feedback-loop/candidates/[id]` (triage form), `/feedback-loop/candidates/new` (manual creation, reachable via a "Create evaluation candidate" link from observability trace detail, conversation detail, review item detail, and evaluation result pages).

`evaluation_candidate_repository.promote_candidate()` requires `triage_status == "accepted"`, builds a new `EvaluationCase` from the candidate's **redacted** content and triage-defined expected outcome, increments `EvaluationDataset.version`, and writes an `EvaluationDatasetVersionEvent` changelog row. See [Dataset Promotion Policy](./Dataset_Promotion_Policy.md) and [Golden Dataset Versioning Guide](./Golden_Dataset_Versioning_Guide.md) for the full policy.

## Scheduled evaluation

Three new CLIs follow the existing `app.operations.eval_run`-style shape (see [Nightly Evaluation VPS Guide](../06_Operations/Nightly_Evaluation_VPS_Guide.md) for cron/systemd examples):

- `app.operations.production_signal_scan` (`npm run feedback:scan`) — runs the detector for one assistant.
- `app.operations.eval_focused_run` (`npm run eval:focused`) — runs only production-fed cases (`EvaluationCase.source_candidate_id is not None`), via a new `EvaluationRunOptions.case_ids` filter in `app.evaluation.engine`.
- `app.operations.eval_regression_report` (`npm run eval:regression-report`) — classifies new/fixed/newly-failing/still-failing cases between two runs, persists an `EvaluationRegressionReport` row.

## Release gate

`app.evaluation.production_gate.evaluate_production_readiness()` (CLI: `app.operations.eval_release_gate_check`, `npm run eval:release-gate-check`) blocks when: an accepted+promoted case still fails in the latest completed run; the latest run has hard failures; isolation-category hard failures or citation coverage regressed vs. the previous baseline; the dataset version changed without a completed run at that version; the baseline is stale (`--max-baseline-age-days`, default 7); or no `EvaluationRegressionReport` exists since the last version bump. Wired into `scripts/release-gate.mjs` as an optional step (`--feedback-loop-organisation/-workspace/-assistant/-dataset`) — skipped, not failed, when those flags aren't supplied, since the generic release gate has no way to infer which assistant to check. See [Regression Release Policy](../06_Operations/Regression_Release_Policy.md).

## Metrics

`app.evaluation.feedback_metrics.compute_feedback_loop_metrics()` — candidates by status/signal/severity, time-to-triage/resolution, failures by root cause, cases added per dataset version, recurrence rate, reopen rate, regression escape rate, fixed-case confirmation rate. Exposed at `GET /workspaces/{id}/evaluation-candidates/metrics`, rendered as tiles on `/feedback-loop`.

## What is not yet built (explicitly out of scope for this cycle)

- **Thumbs-down capture**: no `ChatMessage` rating column, no widget-side feedback UI (`apps/widget`/`packages/widget-sdk`). The `thumbs_down` signal type exists in the schema for forward compatibility only.
- **Semantic duplicate detection**: only deterministic hash + token-overlap matching exists; embedding-based similarity was scoped out to avoid a new heavy dependency (per-candidate embedding calls/storage) for this iteration.
- **Automatic multi-tenant nightly scanning**: `production_signal_scan` requires an explicit `--organisation/--workspace/--assistant` per invocation, matching every other `eval_*` CLI in this codebase; a fleet-wide nightly job loops the CLI per assistant rather than the CLI enumerating tenants itself.
- **Automatic promotion**: never happens — every promotion requires an explicit `accepted` human decision, per the original spec's "No automatic approval."

## What changed since v1.0

v1.0 (design-only) proposed a "lightweight append-only log (JSON file or table)" for intake — implemented as the `EvaluationCandidate` table directly, since a full DB model (not a log) is what the triage UI, dedup, and promotion workflow all need. v1.0's `triage_status` sequence (`new → reproduced → case_created → fix_in_progress → regression_verified → closed`) was refined to the implemented `new/triaged/needs_information/accepted/rejected/duplicate/resolved` set, which distinguishes "not a real issue" (`rejected`), "same as another candidate" (`duplicate`), and "promoted and later confirmed fixed" (`resolved`) as separate terminal states rather than one `closed` state. Everything else (redaction reuse, additive dataset versioning, no engine special-casing for production-derived cases, no automated guardrail/grader action) matches the original design.
