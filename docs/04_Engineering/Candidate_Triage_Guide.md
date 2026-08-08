# Candidate Triage Guide

Related: [Production Feedback Loop](./Evaluation_Production_Feedback_Loop.md), [Dataset Promotion Policy](./Dataset_Promotion_Policy.md).

Audience: reviewers (`org_owner`/`client_admin`) working the `/feedback-loop` queue.

## Where candidates come from

Most candidates are created automatically by `app.operations.production_signal_scan` (nightly, per assistant — see the [Nightly Evaluation VPS Guide](../06_Operations/Nightly_Evaluation_VPS_Guide.md)). Some are created manually via the "Create evaluation candidate" link on an observability trace, a conversation, a review item, or a failing evaluation result — this is the path for support-reported issues, grader-advisory failures, and anything a reviewer wants to flag by hand.

## Status lifecycle

```
new → triaged → accepted → (promote) → resolved
        ↓            ↓
  needs_information  rejected
        ↓
    duplicate
```

- **`new`** — untouched since creation/last recurrence.
- **`triaged`** — a reviewer has looked at it and assigned a root cause, but hasn't decided accept/reject yet.
- **`needs_information`** — can't be triaged yet (e.g. the linked trace/conversation was purged, or the question is ambiguous). Not terminal — comes back to `triaged` once resolved.
- **`accepted`** — confirmed real defect, ready to promote into a golden dataset. This is the *only* status `promote_candidate()` will act on.
- **`rejected`** — reviewed and determined not a real defect (expected behaviour, user error, one-off fluke). Terminal.
- **`duplicate`** — the same underlying issue as another candidate (`duplicate_of_id` points at it). Terminal. Use "Mark duplicate of" on the detail page rather than silently ignoring — this feeds the recurrence/reopen metrics.
- **`resolved`** — promoted and the loop closed (confirmed fixed by a later regression run, or otherwise closed out). Terminal.

Terminal statuses (`rejected`/`duplicate`/`resolved`) cannot be re-triaged — the API returns `422` (`InvalidTriageTransition`). If a "fixed" issue recurs, the detector creates a **new** candidate flagged `is_reopen=True` rather than reopening the old one; the old row's terminal status is an honest historical record.

## What to fill in before accepting

- **Root cause category** — reuse the existing evaluation taxonomy (`app.evaluation.categories.CaseCategory`), not a new vocabulary. If nothing fits, use the closest match and say why in notes.
- **Severity** — `low`/`medium`/`high`/`critical`. Automatic signals start conservative (see the [Production Feedback Loop](./Evaluation_Production_Feedback_Loop.md) doc's escalation rule); a reviewer should override it based on real customer impact, not just recurrence count.
- **Expected outcome** — `expected_document_ids`/`expected_source_labels`/`expected_answerability`, plus anything softer (required/forbidden answer points, citation/fallback/clarification requirements) in `triage_details`. These map directly onto the `EvaluationCase` created at promotion time.

## Duplicate suggestions

The candidate detail page shows deterministic duplicate suggestions (exact dedup-hash match, or ≥60% word-overlap with another open candidate for the same assistant — see `app.evaluation.feedback.dedup`). These are suggestions only; nothing is auto-merged. Mark a genuine duplicate explicitly so the recurrence isn't double-counted in the golden dataset.

## Promotion

Only from `accepted`. Requires a target dataset id and an optional changelog note (shown in [Dataset Versions](./Golden_Dataset_Versioning_Guide.md)). After promotion, run a focused evaluation (`npm run eval:focused`) to confirm the new case actually reproduces (and, after a fix ships, passes) — an accepted case that already passes on the current code before any fix isn't a useful regression case; re-examine whether it was really a defect.
