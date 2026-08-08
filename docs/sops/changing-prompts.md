# SOP: Changing Prompts

## Purpose

Change a prompt template safely under the immutable-versioning model (ADR 0003).

## When to use

Any change to prompt template text, structure, or the context it's assembled from.

## Step-by-step process

1. Never edit an `active` prompt version's template in place — create a new version in `draft` status.
2. Move `draft → testing` once ready for evaluation.
3. Run the full evaluation case set against the `testing` version (`docs/checklists/evaluation-checklist.md`).
4. Shadow-test against production traffic samples per `docs/future/PromptOptimisation.md`.
5. Compare grader scores (`docs/engineering/graders.md`) against the current `active` version — no regression on gating dimensions.
6. Promote `testing → active` only once promotion criteria are met; the previous `active` version moves to `deprecated`.

## Validation

`docs/checklists/evaluation-checklist.md`; `prompt_key`/`prompt_version`/`prompt_hash` correctly recorded on affected messages.

## Rollback

Deprecate the newly-active version, revert to the prior `active` version — full traceability via the hash-based versioning means this is always safe and immediate.

## Success criteria

New version promoted only after passing evaluation with no gating-dimension regression; every message using the new version is traceable to its exact template via `prompt_hash`.
