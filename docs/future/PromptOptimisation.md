# Prompt Optimisation

## Purpose

Systematically improve prompt templates using evaluation data, and support A/B or shadow-testing between prompt versions before promoting a new version to `active`.

## Current limitation

`docs/engineering/prompt-versioning.md` — prompts are versioned and traceable, but there is no A/B testing mechanism between versions; promotion from `testing` to `active` is a manual, evaluation-informed but not automated, decision.

## Why postponed

Needed the versioning/traceability foundation (ADR 0003) and the evaluation framework (`docs/architecture/evaluation.md`) to exist and stabilize first — optimizing prompts without reliable measurement would be guesswork.

## Dependencies

- Stable evaluation framework with launch-gating deterministic scoring and calibrated grader dimensions (`docs/engineering/graders.md`).
- Sufficient production traffic/evaluation case volume to make A/B comparisons statistically meaningful.

## Implementation phases

1. Formalize a shadow-testing mode: run a `testing`-status prompt version against a sample of real (or evaluation-case) requests without serving its output, comparing grader scores to the current `active` version.
2. Add explicit promotion criteria (e.g. no regression on any gating dimension, improvement on at least one advisory dimension) before a version can move `testing → active`.
3. Automated regression detection: flag if a newly-promoted version's live grader scores diverge from its shadow-test results.

## Technical design

Builds directly on the existing prompt lifecycle (`draft → testing → active → deprecated → retired`, ADR 0003) — this adds tooling around the `testing` state, not a new lifecycle state.

## Evaluation plan

Every candidate prompt version evaluated against the full case set before promotion; promotion criteria enforced as a gate, not a suggestion (matching the deterministic-evaluation-gate philosophy, ADR 0025).

## Rollback strategy

Prompt versioning is already immutable/append-only (ADR 0003) — rollback is deprecating the newly-active version and reverting to the prior `active` version, with full traceability via `prompt_key`/`prompt_version`/`prompt_hash` on affected messages.

## Success metrics

Measurable grader-score improvement release-over-release, with zero un-evaluated prompt promotions.
