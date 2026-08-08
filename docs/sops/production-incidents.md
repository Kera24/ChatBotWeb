# SOP: Production Incidents

## Purpose

General-purpose response process for any production incident not covered by a more specific SOP/runbook.

## When to use

An alert fires, a customer reports a broken experience, or observability shows an anomaly with no immediately obvious specific cause.

## Step-by-step process

1. Triage: check `/observability` dashboard for the affected time window — identify scope (one tenant vs. all, one feature vs. platform-wide).
2. Identify the most specific matching `docs/runbooks/*.md` for the symptom pattern; if none matches exactly, use the closest one as a starting structure.
3. Stabilize first (rollback, disable a flag, route around a failing dependency) before root-causing — restoring service takes priority over full diagnosis.
4. Once stable, root-cause using traces (`ai_traces`/`ai_trace_stages`/etc.), logs, and recent deployment history.
5. Fix, following the applicable checklist/SOP for the affected subsystem.
6. Post-incident review: what happened, why, what changes (code, process, or a new runbook/case) prevent recurrence.

## Validation

Service restored and confirmed via dashboard/smoke checks; root cause documented; a concrete follow-up action identified (not just "monitor").

## Rollback

`docs/sops/rollback.md` if the incident is deployment-attributable.

## Success criteria

Service restored quickly; root cause understood and documented; a specific preventive action (test case, guardrail, alert, runbook) results from the review, per `docs/operations/continuous-improvement.md`.
