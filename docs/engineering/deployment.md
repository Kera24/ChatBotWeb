# Deployment — Current / Future / Out of Scope

## Current

VPS-hosted via `docker-compose.prod.yml` (Compose project `chatbotweb-prod`), optional additive `docker-compose.observability.yml`. Azure infra (`infrastructure/azure/`) kept live but not the active deployment target. Full detail: `docs/architecture/deployment.md`. Decision record: ADR 0018 (original Azure-first pilot architecture), ADR 0027 (VPS-first pivot, supersedes 0018's hosting choice), ADR 0029 (retain Azure IaC without deploying).

## Future

- Promotion to Azure (or another cloud target) once VPS-scale evidence shows it's warranted — see `docs/future/DeploymentRoadmap.md` and `docs/future/ScalingRoadmap.md`.
- GPU-backed inference workers, if/when a self-hosted model is introduced — see `docs/future/GPUWorkers.md`.

## Out of scope (not planned)

- Multi-cloud active-active deployment — not planned at any current or near-term scale tier (see `docs/engineering/scaling-strategy.md`).
