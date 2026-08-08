# SOP: Hotfix

## Purpose

Ship an urgent, narrowly-scoped fix outside the normal release cadence, per `docs/releases/emergency-hotfix.md`'s entry/exit criteria.

## When to use

A production-impacting defect that can't wait for the next normal release cycle — never for convenience or to skip review.

## Step-by-step process

1. Scope the fix as narrowly as possible — a hotfix is not an opportunity to bundle unrelated changes.
2. Run the narrowest test suite that covers the fix, plus the full suite for the affected area (`docs/validation-policy.md`).
3. Skip non-essential process (extended monitoring windows, non-critical documentation) but never skip: tests, evaluation (if AI-pipeline-touching), security review (if security-relevant), and RBAC/tenant-isolation checks.
4. Get expedited approval per `docs/releases/emergency-hotfix.md`.
5. Deploy per `docs/sops/deploying.md`, with heightened post-deploy monitoring.
6. Follow up with the normal-cadence documentation/cleanup within a short window (the shortcut is speed of approval, not permanent reduced rigor).

## Validation

Tests for the affected area pass; evaluation gate passes if AI-pipeline-touching; no `--no-verify`/skipped hooks.

## Rollback

`docs/sops/rollback.md`, with the hotfix's narrow scope making rollback low-risk by design.

## Success criteria

Production defect resolved; fix scope stayed narrow; no unrelated changes bundled in; follow-up documentation completed within the agreed window.
