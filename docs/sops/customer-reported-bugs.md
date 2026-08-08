# SOP: Customer Reported Bugs

## Purpose

Turn a customer bug report into a diagnosed, fixed, and evaluated change.

## When to use

Any inbound report of incorrect, missing, or unexpected behavior from a tenant.

## Step-by-step process

1. Reproduce: get enough detail (conversation ID, workspace, approximate time) to pull the actual trace from `/observability`, not just the customer's description.
2. Classify: RAG-quality issue (wrong/ungrounded answer), guardrail issue (incorrectly blocked or incorrectly allowed), UI/product issue, or billing/auth issue — route to the matching SOP.
3. For RAG-quality issues: add the case to the evaluation set (`docs/sops/evaluation-failures.md`'s process) so the specific failure is captured permanently, not just patched once.
4. Fix following the standard lifecycle (`docs/workflows/engineering-lifecycle.md` or `docs/workflows/feature-development.md`).
5. Confirm the fix with the customer's original scenario, not just the new evaluation case in isolation.

## Validation

The specific reported scenario now behaves correctly; a corresponding evaluation/test case exists so it can't silently regress.

## Rollback

Standard rollback per the fix's own SOP (deploy rollback, prompt revert, etc.) if the fix itself causes a new issue.

## Success criteria

Customer's reported scenario resolved and confirmed; a permanent test/evaluation case exists for it; customer notified of resolution.
