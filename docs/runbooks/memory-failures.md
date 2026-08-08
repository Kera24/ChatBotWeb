# Runbook: Memory Failures

Applies once `docs/future/MemoryV2.md` is implemented.

## Symptoms

A conversation shows evidence of incorrect memory behavior: context from a different conversation/tenant leaking in (critical — treat as a security incident), or expected context missing/stale.

## Diagnosis

1. **First determine if this is a privacy/isolation breach** (cross-conversation or cross-tenant context leak) — if so, stop and switch immediately to `docs/sops/security-incident.md`, this runbook does not apply.
2. If it's a correctness-only issue (memory scoped correctly but stale/missing/wrong within the *same* conversation): pull the memory-injection trace for the specific request (`docs/checklists/memory-checklist.md`'s traceability requirement) to see what context was actually injected.
3. Check for a recent memory-logic change correlated with the issue.

## Recovery

1. Privacy/isolation issue: contain immediately (disable memory feature flag platform-wide if scope of the leak is unclear), follow `docs/sops/security-incident.md` in full.
2. Correctness-only issue: fix the context-assembly logic, add a reproducing test to the multi-turn evaluation case set.
3. Consider flag-disabling memory for the affected tenant/conversation while investigating, falling back to the always-available no-memory behavior.

## Validation

For privacy issues: `docs/checklists/security-checklist.md` in full, scope of exposure precisely bounded. For correctness issues: the specific scenario now behaves correctly and is covered by a test.

## Escalation

Any privacy/isolation-adjacent memory failure escalates immediately and is never treated as "just a bug" — the flag-disable fallback to current no-memory behavior exists specifically for this reason.

## Post-incident review

If this was a privacy breach: full security-incident post-review process. If correctness-only: was memory's own test coverage the gap, and does this change the risk assessment for memory's rollout pace.
