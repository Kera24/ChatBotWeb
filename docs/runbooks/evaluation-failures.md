# Runbook: Evaluation Failures (Production-Detected)

## Symptoms

Continuous evaluation (`docs/future/EvaluationV2.md`, once implemented) or a manual production-trace review reveals a quality regression not caught pre-release.

## Diagnosis

1. Identify the specific failure pattern from production traces (`ai_traces`, grader scores if available).
2. Determine whether the pre-release evaluation case set had a gap (didn't cover this scenario) or whether something changed post-release without going through evaluation (a process gap).
3. Reproduce the failure against the current evaluation case set to confirm it's a real, repeatable pattern.

## Recovery

1. Add the failure pattern as a new evaluation case (`docs/sops/evaluation-failures.md` covers the pre-release version of this SOP — this runbook is the production-detection trigger for that same process).
2. Fix the underlying cause (prompt, retrieval, guardrail, or model issue) following the matching SOP.
3. Re-run the full evaluation gate before re-deploying the fix.

## Validation

New case added and passing after the fix; full evaluation gate green; production trace review confirms the pattern has stopped recurring.

## Escalation

A pattern that reveals a systemic evaluation-coverage gap (not just one missing case) escalates to a broader evaluation-case-set review.

## Post-incident review

This is exactly what `docs/roadmap/roadmap.md`'s Golden Dataset Update stage exists for — confirm the finding is captured there, and note whether continuous evaluation (`docs/future/EvaluationV2.md`) would have caught this sooner.
