# Continuous Evaluation Privacy and Redaction Policy

Status: implemented
Related: [AI Trace Data and Privacy Policy](./AI_Trace_Data_and_Privacy_Policy.md), [AI Trace Retention and Redaction Guide](./AI_Trace_Retention_and_Redaction_Guide.md), [Production Failure Intake Runbook](../06_Operations/Production_Failure_Intake_Runbook.md).

This document covers `EvaluationCandidate` rows specifically — a different retention posture from AI traces, because a candidate is content a human reviewer is expected to read (to triage it), not metadata for automated dashboards. See the linked AI Trace policy for how production traces themselves are handled; this document is about what happens when a trace/conversation/message becomes a candidate.

## What is captured

`EvaluationCandidate.redacted_question`/`redacted_response` **always** — unconditionally, with no content-mode toggle like `AITrace.content_mode` — pass through `app.observability.redaction.redact_free_text` before being written, whether the candidate came from the automatic detector (`app.evaluation.feedback.detector`) or a human filling in the manual-creation form (`app/api/v1/evaluation_candidates.py::create_candidate`). There is no code path that writes unredacted text into this table. `redaction_version` (currently `app.observability.redaction.REDACTION_RULESET_VERSION = "v1"`) is stored alongside the text so a later audit can tell which ruleset produced it if the pattern set changes.

## What is never captured

- **Quoted chunk content.** `evidence_refs_json` is restricted to `{document_id, chunk_id, source_title}` — never `Citation.quoted_text` or any other excerpt of document content. A reviewer who needs to see the actual source text follows the structural reference through the existing, RBAC-gated document/citation endpoints, not through anything stored on the candidate itself.
- **Raw production prompts in version-controlled fixtures.** Promotion (`promote_candidate()`) only ever writes to the `evaluation_cases` DB table; it has no code path that touches `app/evaluation/fixtures/*.json` or any other file under version control. Even the redacted text that does get promoted into a golden `EvaluationCase` never becomes a git-tracked fixture automatically.
- **Unstructured free text beyond question/response/notes.** No full-conversation dump, no arbitrary metadata blob containing customer content — `metadata_json` on a candidate only ever holds structured signal detail (e.g. `{"error_code": ..., "guardrail_name": ...}`), never re-derived content.

## Redaction ruleset

Identical patterns to the AI trace policy (`redact_free_text` is the same function, called from both places): Stripe secret keys, Stripe webhook secrets, AWS access keys, JWTs, bearer tokens, database connection strings, this codebase's public widget keys (pseudonymised) and session tokens, any deployment-specific `AI_TRACE_CUSTOM_REDACTION_PATTERNS`, then generic email/phone PII. Structural secrets are matched first. See the AI Trace policy for the exact pattern list and rationale — it is not duplicated here to avoid the two documents drifting out of sync.

## Access control

Same RBAC shape as everywhere else in this feature: `org_owner`/`client_admin`/`viewer` can read candidates (including redacted question/response text — unlike AI trace content previews, there is no additional gate beyond the standard read role, since redaction has already been applied before storage); `org_owner`/`client_admin` can triage, mark duplicates, and promote. Cross-organisation/cross-workspace lookups return 404, never 403 (no existence leakage) — see `app/api/v1/evaluation_candidates.py`'s `_ensure_workspace` guard, matching every other tenant-scoped route in this codebase.

## Deduplication and privacy

`dedup_hash` is a SHA-256 hash of a normalized question, not a reversible encoding — it cannot be used to recover the original text, only to detect exact/near-exact repeats. Duplicate suggestions shown to reviewers (`app.evaluation.feedback.dedup.find_potential_duplicates`) only ever compare **already-redacted** text against other already-redacted text; no raw production content is ever compared or exposed during deduplication.

## What is explicitly out of scope

Encryption-at-rest for candidate content beyond the database's own storage-level encryption (if any, deployment-dependent) is not implemented — matching the AI Trace policy's `encrypted_full_content` mode, which is also not implemented. If a future requirement needs stronger-than-redaction protection for candidate text, that is a KMS/key-management decision affecting both this table and `ai_traces`, and should be designed once, not per-table.
