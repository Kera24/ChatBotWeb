# SOP: Evaluation Failures

## Purpose

Respond correctly when an evaluation gate fails, without weakening the gate.

## When to use

Any `npm run eval:test` or evaluation-gate run that fails to meet the deterministic threshold.

## Step-by-step process

1. Read the failing case(s) — identify exactly which scoring dimension and which case regressed.
2. Reproduce locally against the specific case, not just the aggregate score.
3. Determine root cause: a real regression in the change under test, a genuinely outdated/wrong case (rare — verify carefully), or a flaky/non-deterministic evaluation issue (should not exist given the deterministic-gate design — investigate as a bug if found).
4. Fix the underlying change — **never loosen the threshold to pass** (`CLAUDE.md`, `docs/adr/0025-deterministic-evaluation-gates.md`).
5. If the case itself is genuinely wrong (rare), fixing it requires explicit review/sign-off, not a unilateral edit.
6. Re-run the full case set after the fix, not just the previously-failing case.

## Validation

Full evaluation-gate re-run passes with no other regressions introduced by the fix.

## Rollback

If the underlying change can't be fixed promptly, revert the change itself rather than the evaluation case or threshold.

## Success criteria

Root cause identified and fixed at the source; thresholds and cases remain unchanged (unless an explicitly reviewed case correction was warranted); full gate passes.
