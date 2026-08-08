# Prompt Versioning Guide

See `docs/architecture/prompts.md` for the data model. This document covers the version lifecycle: how a `PromptVersion` moves through states, and the invariants that hold at every step.

## Status machine

```
draft ──────────────► under_evaluation ──────────────► approved ──────► (deploy) ──► active
                              │                              │
                              ├──► rejected                  └──► rejected
                              └──► draft (send back for edits)

active ──► superseded   (a newer version was deployed over it)
active ──► rolled_back  (a rollback restored the previous version)
superseded/rolled_back ──► active  (a rollback can restore a previously-deployed version)
```

`app.repositories.prompt_repository._PRE_DEPLOY_TRANSITIONS` is the authoritative transition map for the pre-deployment states (`draft`/`under_evaluation`/`approved`/`rejected`), enforced by `transition_version_status()` — any other transition raises `InvalidVersionTransition`. The `active`/`superseded`/`rolled_back` states are not reached via `transition_version_status()` at all; they're a side effect of `deploy_version()` and `rollback_deployment()`, which have their own preconditions (`deploy_version()` requires `status == "approved"`, raising `VersionNotApproved` otherwise).

## Immutability

A `PromptVersion` row is never edited in place after creation — `content`, `checksum`, and `variables_schema_json` are fixed at creation time. A "change" always means creating a new version via `create_draft_version()`, optionally with `parent_version_id` pointing at the version it's meant to supersede (for lineage/diffing, not enforced ordering). Rollback never deletes a version row — a rolled-back version stays fetchable and its full history stays in `PromptAuditEvent`.

## Checksums

`app.prompts.render.layer_checksum()` computes a sha256 over `layer + version_number + content + variables_schema` at creation time — this is per-layer. The composite checksum for a rendered request (`app.prompts.render.composite_checksum()`) is a sha256 over the ordered list of each resolved layer's checksum, stamped into `AIModelCallTrace.prompt_hash` (see the composite-identity section of `docs/architecture/prompts.md`).

## Diffing

`app.repositories.prompt_repository.diff_versions()` is a simple `difflib.unified_diff` over two versions' `content` — deliberately not a rich visual diff tool (see the explicit scope cut in `docs/architecture/prompts.md`). Diffing a platform-immutable layer's versions requires `super_admin`, same redaction rule as viewing content directly.

## Approval

Approving a version (`transition_version_status(new_status="approved")`) stamps `approved_at`/`approved_by_user_id` but does **not** itself run the evaluation gate — approval and evaluation are deliberately separate actions (see `docs/04_Engineering/Prompt_Evaluation_and_Promotion_Policy.md`); nothing in the versioning API forces a gate run before approval, since a reviewer may reasonably want to inspect a gate's result (via `POST .../versions/{id}/evaluate`) before deciding to approve. `deploy_version()` is the only hard gate: it requires `status == "approved"`, but does not itself re-check the evaluation gate result — that's a deliberate human-in-the-loop step, mirroring this codebase's existing "no automatic-promotion path" rule for evaluation candidates (`docs/file-boundaries.md`'s Continuous Evaluation section).
