# Production Feedback Loop

Version: 1.0
Status: Design only in this cycle - no runtime collection is implemented yet (see "What is not yet built" below).
Related: [Evaluation Framework](./Evaluation_Framework.md), [Final Report](./Evaluation_Final_Report.md)

## Purpose

Every production failure an assistant makes is a candidate golden-dataset case. Without a deliberate loop feeding real failures back into the evaluation dataset, the golden dataset only ever tests what its authors already imagined - it never learns from what actually goes wrong for real customers. This document designs that loop; implementing the runtime collection plumbing is future work (this cycle is evaluation-and-improvement on the *existing* pipeline, not new instrumentation).

## Signals to capture

All of these are already partially observable in the existing data model (`ChatMessage.answer_state`, `Citation`, `ReviewAnnotation`) or existing product surfaces (the Knowledge Gaps / review queue). The feedback loop's job is to systematically route them into golden-dataset candidates, not to invent new telemetry from scratch:

- Fallback responses (`ChatMessage.answer_state == "fallback"`)
- Low-confidence responses (`answer_state == "low_confidence"`)
- Failed answers (`answer_state == "failed"`)
- Missing citations (an "answered" message with zero `Citation` rows)
- Invalid citations (a citation referencing a chunk/document outside the assistant's authorised scope - should never happen given the isolation guarantees, but must be treated as a P0 if ever observed)
- User thumbs-down (wherever that signal exists in the conversation/review UI)
- Unresolved review-queue items (`ReviewAnnotation` rows past a staleness threshold)
- Customer-reported bad answers (support tickets, direct feedback)
- High latency (`ChatMessage` latency significantly above the configured `EvaluationPolicy.max_p95_latency_ms`)
- Provider failures (`answer_state == "failed"` with a provider-execution error reason)
- Unusual retrieval scores (very low top-1 score on an "answered" response - only meaningful once a real, semantically-informative embedding provider is in place per the Final Report's blocker)
- Cross-scope denial events (`RAGTenantContextError` raised in production - should be rare/zero; a spike is itself a signal worth investigating, not just a case to add)

## Per-failure workflow

For each meaningful production failure:

1. **Reproduce it safely.** Re-run the exact query against the same assistant/knowledge scope in a non-production, isolated evaluation context (the same `shadow_rag_session()` mechanism the evaluation engine already uses guarantees this reproduction never touches real conversation history).
2. **Redact customer-sensitive content.** Before the failure is stored anywhere outside the live conversation record, strip anything customer-identifying (names, account IDs, free-text PII) using the same pattern-based redaction already implemented for evaluation error messages (`app/evaluation/redaction.py::redact_secrets`/`safe_error_message`) - extended, if needed, with additional customer-PII patterns rather than a new mechanism.
3. **Create a new golden evaluation case** via the existing `EvaluationCase` API (`POST /api/v1/workspaces/{workspace_id}/evaluation/datasets/{dataset_id}/cases`) - no new infrastructure needed, since the case schema already supports everything this needs (`question`, `category`, `expected_answerability`, `expected_document_ids`, `tags`, `metadata_json` for a `"source": "production_failure"` provenance tag and a `"redacted_from"` reference).
4. **Add the expected outcome** based on what the assistant *should* have done (informed by the redacted original question and the correct document(s), if any).
5. **Run the current baseline** against just this new case (`eval:run -- --category <its category>` or by running the single dataset) to confirm it currently reproduces the failure (a new case that already passes on the current code is not a useful regression case - re-examine whether it was really a defect).
6. **Fix the root cause**, following the same root-cause classification taxonomy as the baseline failure analysis (missing source data, retrieval miss, chunking problem, prompt problem, etc.).
7. **Run the full regression suite** (`eval:test` plus the full golden dataset) to confirm the fix resolves the new case without regressing any existing one, using the same baseline-vs-candidate comparison methodology in this cycle's [Comparison Report](./Evaluation_Comparison_Report.md).
8. **Deploy only after** both the new case and every previously-passing case pass.

## Repository structure for this workflow

- **Production-failure intake**: a lightweight, append-only log (initially a simple JSON file or a dedicated low-traffic table - not designed in this cycle) recording `{production_message_id (internal only, never exported), redacted_question, observed_answer_state, observed_citations, reported_by, reported_at, triage_status}`.
- **Case triage**: a `triage_status` field (`new` → `reproduced` → `case_created` → `fix_in_progress` → `regression_verified` → `closed`) tracked alongside the intake log entry, cross-referenced to the resulting `EvaluationCase.id` once created.
- **Redaction**: reuse `app/evaluation/redaction.py`; extend its pattern list under version control (a code change, reviewed like any other) rather than an ad-hoc per-case manual redaction step, so redaction quality itself is consistent and auditable.
- **Dataset versioning**: production-derived cases are added to the *existing* golden dataset with an incremented `EvaluationDataset.version` (already a first-class field) and tagged `tags: ["production-derived"]` so they can be filtered and reported on separately from the originally-authored cases, without needing a second dataset.
- **Regression inclusion**: production-derived cases participate in every future full-dataset run identically to hand-authored cases - no special-casing in the engine, matching the principle that a golden dataset should measure the real system the same way regardless of a case's origin.
- **Release-note linkage**: each deployed fix referencing a production-failure case should cite the `EvaluationCase.id` (and, once implemented, the intake log entry) in its commit message and release notes, so a future reader can trace "why does this case exist" back to the original incident without re-deriving it from the code alone.

## What is not yet built (explicitly out of scope for this cycle)

- Automated production-signal capture/alerting (this document specifies *what* to capture and *how it flows into the dataset*, not a new telemetry pipeline).
- The intake log's actual storage mechanism (file vs. table) - a decision for whoever implements this, informed by production traffic volume once real usage exists.
- Any guardrail enforcement action taken automatically in response to a detected failure pattern - guardrails are explicitly out of scope for this task and the next one in this workstream.
- Model-as-judge scoring of production answer quality - also explicitly out of scope for this task.
