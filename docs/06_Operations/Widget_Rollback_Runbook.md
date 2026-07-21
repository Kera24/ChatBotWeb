# Widget Rollback Runbook

Status: TASK-066B3 dry-run rollback planning

## Principles

- Never overwrite immutable semantic SDK artifacts.
- Rollback should use previous known-good artifacts.
- SDK, iframe, and backend rollback can be independent only within the documented protocol/API compatibility range.

## Plan Rollback

```bash
npm run widget:rollback:plan -- artifacts/widget-release/manifest.json path/to/known-good-manifest.json
```

The command is dry-run only. It validates protocol major and API version compatibility and prints:

- target SDK immutable version
- major alias path
- immutable loader path
- target commit
- required smoke tests

## Required Verification

Before and after rollback:

```bash
npm run widget:release:build
npm run widget:pilot:verify
npm run widget:pilot:readiness
```

Post-deploy environments must additionally verify headers, cache policy, real config/session/message smoke, tenant isolation, and token isolation.

## SDK Alias Rollback

Repoint or replace the mutable major alias to a previous known-good loader copy. Do not mutate the immutable semantic loader path.

## Iframe Rollback

Restore the previous iframe HTML/release mapping that references known-good hashed assets. Do not overwrite hashed immutable assets.

## Backend Rollback

Roll back the backend artifact through deployment infrastructure. Validate migrations are rollback-compatible before proceeding.


## Azure Rollback Foundation

TASK-068B1 defines Azure deployment units for future rollback automation: API Container App revision, web Container App revision, SDK major alias/static asset publication, iframe static artifact, and migration job. B1 does not execute rollback or deploy a known-good production artifact.

TASK-068B2 must automate rollback planning and release promotion against these units before production pilot deployment.

## Azure TASK-068B2 Rollback Operations

Azure rollback is now planned through deployment manifests:

```bash
npm run azure:rollback:plan -- --current <current-manifest> --to <target-manifest>
```

The planner blocks automatic rollback when protocol major, public API version, or Alembic migration head differ. Database downgrade is not automated.

Azure rollback workflow:

1. Download current deployment manifest.
2. Download known-good target deployment manifest.
3. Run rollback planner.
4. If compatible and approved, update API/web Container Apps to target image refs.
5. Restore target widget static release.
6. Repoint SDK major alias through static publication.
7. Run deployed smoke.
8. Preserve rollback evidence.

Do not overwrite immutable SDK semantic paths. If immutable artifacts already exist with a different checksum, rollback must fail rather than mutate history.
