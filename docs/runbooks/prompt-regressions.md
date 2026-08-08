# Runbook: Prompt Regressions

## Symptoms

Grader scores, fallback rate, or evidence-insufficient rate shift negatively in production, traced to a specific `prompt_version`.

## Diagnosis

1. Correlate the shift's onset with the prompt version's promotion timestamp (`prompt_key`/`prompt_version`/`prompt_hash` on affected messages).
2. Pull representative regressed traces to characterize the failure pattern (over-citing, under-citing, tone drift, refusal-rate change, etc.).
3. Confirm this wasn't caught in pre-promotion evaluation — check whether the evaluation case set covered this scenario.

## Recovery

1. Immediate: revert to the prior `active` prompt version (`docs/sops/prompt-failures.md`) — always safe and fast given immutable versioning.
2. Root-cause: draft a fixed version following `docs/sops/changing-prompts.md`'s full process.
3. Add the failure pattern as a new evaluation case before re-promoting.

## Validation

Reverted version's grader scores back at baseline; fixed version passes the full evaluation gate including the new case before re-promotion.

## Escalation

If this is the second+ regression from the same prompt-change process, escalate to reviewing whether `docs/future/PromptOptimisation.md`'s shadow-testing needs to be mandatory rather than optional.

## Post-incident review

Was the evaluation case set's coverage the gap, or was the promotion criteria itself too loose? Feeds `docs/engineering/prompt-versioning.md` and the Golden Dataset Update stage.
