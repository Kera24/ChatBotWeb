# TASK-002 Backend Foundation Prompt

Use this prompt in Cursor, Codex, or Claude Code to implement TASK-002.

```text
You are implementing TASK-002: Backend Foundation in the ChatBotWeb / Yoranix AI Platform repository.

Read first:

- README.md
- apps/api/README.md
- planning/tasks/TASK-002-backend-foundation.md
- implementation-pack/README.md
- implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md
- implementation-pack/04_Backend/01_Backend_Engineering_Standards.md
- docs/02_Architecture/03_API_Specification.md
- docs/07_Roadmap/01_MVP_Implementation_Plan.md

Objective:

Turn the current FastAPI placeholder into a clean backend foundation.

Scope:

Create or update:

- apps/api/app/main.py
- apps/api/app/core/config.py
- apps/api/app/api/v1/router.py
- apps/api/app/api/v1/system.py
- apps/api/tests/test_health.py
- apps/api/tests/test_system.py
- apps/api/requirements.txt
- apps/api/pytest.ini or pyproject test config if needed
- __init__.py files where needed

Requirements:

1. Use a create_app() factory in main.py.
2. Load basic settings from a central config module.
3. Keep /health at the root level.
4. Put /api/v1/system/info in the v1 router.
5. Return stable JSON responses.
6. Add pytest tests using FastAPI TestClient.
7. Do not implement auth, database, RAG, Redis, or external AI providers yet.
8. Keep dependencies minimal.

Expected endpoint behaviour:

GET /health
returns HTTP 200 and JSON containing:

- status: ok
- service: chatbotweb-api

GET /api/v1/system/info
returns HTTP 200 and JSON containing:

- name: ChatBotWeb / Yoranix AI Platform
- version: 0.1.0
- phase: mvp-foundation

Acceptance criteria:

- FastAPI app imports cleanly.
- API starts with uvicorn app.main:app --reload from apps/api.
- Health endpoint test passes.
- System info endpoint test passes.
- No unrelated feature work is added.

After implementation, report:

- Files changed
- Tests added
- Commands to run locally
- Any assumptions
```
