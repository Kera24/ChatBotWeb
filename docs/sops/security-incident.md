# SOP: Security Incident

## Purpose

Respond to a suspected or confirmed security issue (tenant-isolation breach, credential leakage, unauthorized access) with urgency and rigor.

## When to use

Any indication of cross-tenant data exposure, RBAC bypass, secret leakage in logs/traces, or unauthorized access — suspected or confirmed.

## Step-by-step process

1. Contain first: if a specific vulnerable path is identified, disable it (flag, route removal, or emergency hotfix) before full root-cause analysis.
2. Assess scope: which tenants/data were potentially exposed, over what time window — query traces/logs to bound this precisely, don't guess.
3. Fix the root cause explicitly (missing `organisation_id`/`workspace_id` filter, RBAC bypass, unredacted logging) — see `docs/checklists/security-checklist.md`.
4. Verify the fix with a test that would have caught the original issue.
5. Determine notification obligations (affected tenants, and any regulatory requirement — see `docs/future/ComplianceRoadmap.md` for the eventual formal process; today this is a manual judgment call requiring escalation, not an automated decision).
6. Post-incident review with security-specific rigor: how did this pass review originally, what check would have caught it.

## Validation

`docs/checklists/security-checklist.md` in full; the specific vulnerability confirmed closed via a reproducing test.

## Rollback

Emergency hotfix (`docs/sops/hotfix.md`) or immediate feature-disable if containment requires it.

## Success criteria

Vulnerability contained and fixed; scope of exposure precisely bounded; affected parties notified per obligation; a new test/check prevents recurrence.
