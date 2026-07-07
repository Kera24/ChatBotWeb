# Task: Backend Foundation

## Task ID

TASK-002

## Linked epic/story

- EPIC-001

## Objective

Turn the API placeholder into a clean FastAPI backend foundation with configuration, modular routing, health checks, and a test structure.

## Context for coding agent

Read these files first:

- apps/api/README.md
- docs/02_Architecture/03_API_Specification.md
- docs/07_Roadmap/01_MVP_Implementation_Plan.md
- planning/epics/EPIC-001-platform-foundation.md

## Files to create or modify

- apps/api/app/main.py
- apps/api/app/core/config.py
- apps/api/app/api/v1/router.py
- apps/api/app/api/v1/system.py
- apps/api/tests/test_health.py
- apps/api/requirements.txt

## Technical requirements

1. Keep FastAPI app modular.
2. Use Pydantic settings or simple configuration structure.
3. Add `/health` endpoint.
4. Add `/api/v1/system/info` endpoint.
5. Add test structure using pytest and FastAPI TestClient.
6. Do not implement database yet.

## Constraints

- No authentication yet.
- No database yet.
- No RAG code yet.
- No external AI provider dependency yet.

## Acceptance criteria

- [ ] FastAPI app imports cleanly.
- [ ] Health endpoint returns status ok.
- [ ] API v1 router exists.
- [ ] System info endpoint exists under API v1.
- [ ] Tests exist for health endpoint.
- [ ] Requirements include only needed dependencies.

## Required tests

- Health endpoint test
- System info endpoint test

## Manual verification

Run API locally and visit:

- `/health`
- `/api/v1/system/info`

## Definition of done

- [ ] Backend foundation implemented
- [ ] Tests added
- [ ] No feature scope creep
- [ ] Ready for database foundation task
