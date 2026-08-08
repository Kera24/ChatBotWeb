# Release Process — Current / Future / Out of Scope

## Current

No formal semantic-versioning/changelog process at the application level (`package.json` root `"version": "0.1.0"`, no `release`/`version` npm scripts). Release/rollback is runbook-driven rather than automated-changelog-driven:

- **CI**: `.github/workflows/` — `azure-deploy-staging.yml`, `azure-infra-whatif.yml`, `azure-promote-pilot.yml`, `azure-rollback.yml`, `azure-validate-staging.yml`, `azure-validate.yml`, `verify.yml`.
- **Runbooks**: `docs/06_Operations/Widget_Deployment_Runbook.md`, `Widget_Rollback_Runbook.md`, `Rollback_Runbook.md`, `Azure_Application_Deployment_Runbook.md`.
- **Widget-specific release model**: ADR 0016 (widget deployment, versioning, and release model) — the widget/embed layer has its own explicit versioning (`managed_major` vs `pinned`) distinct from the application's own lack of one.

## Future

- A repo-level changelog and semantic version bump discipline for the API/web apps themselves, once release cadence increases beyond the current pilot stage — see `docs/roadmap/roadmap.md`.
- Automated release notes generated from evaluation-run results (only ship a version whose evaluation gate passed) — ties into `docs/engineering/evaluation.md`.

## Out of scope (not planned)

- Adopting a release process for the core application faster/looser than the widget's own versioned release model (ADR 0016) — any future process should be at least as strict, not looser.
