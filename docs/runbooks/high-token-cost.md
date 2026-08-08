# Runbook: High Token Cost

## Symptoms

Cost-spike alert fired (`docs/architecture/observability.md`), or aggregate cost trend rising unexpectedly.

## Diagnosis

1. Query `ai_model_call_traces` grouped by workspace/model/day to isolate the source — one tenant, one assistant, or platform-wide.
2. Check for abnormal query patterns (very long prompts, unusually high `top_k` retrieval, a retry loop generating repeated calls).
3. Check whether `pricing_known=False` traces exist (unknown pricing being miscounted) — verify `cost_calc_version`/per-token pricing is correctly configured.
4. Check for a recent prompt-length or retrieval-parameter change correlated with the spike.

## Recovery

1. If a retry loop or bug is causing repeated calls: fix the bug (likely a `docs/sops/model-failures.md` or pipeline issue), don't just absorb the cost.
2. If a specific tenant's legitimate usage grew: this may be expected — confirm against their plan tier, not an incident.
3. If prompt length grew unnecessarily: `docs/future/PromptOptimisation.md`/`docs/future/CostOptimisation.md` territory — not an emergency fix, a planned improvement.

## Validation

Cost trend returns to expected baseline, or is confirmed as legitimate usage growth (not an incident).

## Escalation

Sustained, unexplained cost growth escalates to a `docs/future/CostOptimisation.md` prioritization discussion.

## Post-incident review

If caused by a bug: add a regression test. If caused by legitimate growth: note it as input to `docs/engineering/scaling-strategy.md`'s cost-implications tracking.
