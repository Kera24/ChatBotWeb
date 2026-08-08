# SOP: Prompt Failures

## Purpose

Respond correctly when an active prompt version produces a quality regression in production.

## When to use

Grader scores, fallback rate, or evidence-insufficient rate shift negatively and are traced back to a specific prompt version (`prompt_key`/`prompt_version`/`prompt_hash` on affected messages).

## Step-by-step process

1. Confirm the regression is attributable to the prompt version via observability trace correlation, not coincidental timing.
2. Do not edit the `active` version's template in place (it's immutable, ADR 0003) — draft a new version with the fix.
3. Follow `docs/sops/changing-prompts.md`'s full evaluation/shadow-test process for the fix.
4. If the regression is severe, deprecate the current `active` version and revert to the last known-good `active` version immediately while the fix is being developed (this is a config-level revert, always available since prompt history is immutable and traceable).

## Validation

`docs/checklists/evaluation-checklist.md`; the reverted or fixed version shows grader scores back at baseline.

## Rollback

Revert to the prior `active` prompt version — always safe and immediate given immutable versioning.

## Success criteria

Regression stopped quickly via revert; root-caused fix goes through the full evaluation process before re-promotion; a case reproducing the failure is added to the evaluation set.
