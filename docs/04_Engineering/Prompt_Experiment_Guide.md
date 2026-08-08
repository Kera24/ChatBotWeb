# Prompt Experiment Guide

See `docs/architecture/prompts.md` and `docs/03_AI/Prompt_Layering_and_Security_Policy.md` for the surrounding context. This document covers `PromptExperiment`: controlled A/B tests of one layer's control vs. candidate version for one widget's traffic.

## Lifecycle

`draft` (created via `create_experiment()`, `safety_gate_state="pending"`) → gate result recorded via `record_candidate_gate_result()` (driven by `app.evaluation.prompt_promotion_gate`, sets `safety_gate_state` to `"passed"`/`"failed"`) → `start_experiment()` (requires `safety_gate_state == "passed"`, raises `ExperimentNotGated` otherwise; sets `status="running"`, `start_at`, and `end_at = start_at + max_duration_hours` if a max duration was set) → `running` → `kill_experiment()` (immediate, sets `status="killed"`, `end_at=now`) or `complete_experiment()` (sets `status="completed"`).

## Deterministic traffic assignment

`app.prompts.experiment_assignment.assign_arm(experiment, unit_key)`: `sha256(f"{experiment.id}:{unit_key}")`, first 8 hex chars as an integer mod 100, compared against `traffic_allocation_percentage` (the candidate's share). `unit_key` is the conversation id where available (falls back to widget id for the first turn), so the same conversation always lands on the same arm for the experiment's lifetime — no state needs to be persisted to make that true.

## Kill switch and duration, checked live

`is_experiment_live()` checks `status == "running"` and the `[start_at, end_at]` window with **no caching** — `app.prompts.resolution`'s 30-second deployment cache never applies to the experiment's own status check, so flipping to `killed` (or reaching `end_at`) takes effect on the very next request, not after up to 30 seconds.

## Exclusion of evaluation/gate traffic

Any request carrying an explicit `prompt_version_override_id` (i.e. an evaluation-engine or promotion-gate call) bypasses experiment assignment entirely — `resolve_composite_prompt()` only looks up a live experiment when `prompt_version_override_id is None`. This falls out of the resolution order naturally; there is no separate "is this eval traffic" flag to keep in sync.

## No cross-tenant mixing

Experiments are created with `organisation_id`/`workspace_id`/`widget_id` all required (unlike deployments, which allow `NULL` for platform scope) — an experiment always belongs to exactly one organisation's one widget. `_experiment_or_404()` in `app.api.v1.prompts` re-validates the fetched row's `organisation_id`/`workspace_id` match the caller's context on every lookup by id.

## Metrics: directional only, by design

`app.prompts.experiment_metrics.compute_experiment_metrics()` computes deterministic per-arm aggregates (request count, fallback rate, failure count, average latency/tokens/cost) via SQL over `AITrace`/`AIModelCallTrace` filtered by `experiment_id`+`experiment_arm` — mirroring `app.evaluation.feedback_metrics`'s pure-aggregation style. **There is no statistical significance testing.** `ArmMetrics.sufficient_sample` (`request_count >= MIN_SAMPLE_SIZE_PER_ARM`, default 100) is a crude minimum-sample-size gate; the frontend (`components/prompts/prompt-experiments-view.tsx`) always labels results as directional and flags arms below the threshold. This is an explicit, documented MVP scope cut (see `docs/architecture/prompts.md`), not an oversight — treat a low-traffic experiment's metrics as anecdotal, not a decision-making input, until real statistical comparison is built.

## Safety-critical experiments

Experiments on the platform-immutable `platform_core` layer require `super_admin` at both create and start time, and are otherwise identical in mechanics to experiments on the two customer-editable layers — see `docs/03_AI/Prompt_Layering_and_Security_Policy.md`'s "Experiments on the platform-immutable layer" section.
