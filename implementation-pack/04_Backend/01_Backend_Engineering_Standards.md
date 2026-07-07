# Backend Engineering Standards

Version: 1.0
Status: Active Draft

## 1. Backend goal

The backend provides the secure API foundation for organisations, workspaces, knowledge management, RAG chat, widget access, analytics, and audit logging.

## 2. Technology baseline

MVP backend stack:

- Python
- FastAPI
- Pydantic
- SQLAlchemy or SQLModel
- Alembic
- PostgreSQL
- Redis for queues and rate limiting
- Pytest for tests

## 3. Folder structure

Target structure:

```text
apps/api/app/
  main.py
  api/
    deps.py
    v1/
      router.py
      system.py
      organisations.py
      workspaces.py
      documents.py
      chat.py
      widget.py
      analytics.py
  core/
    config.py
    logging.py
    errors.py
    security.py
  db/
    session.py
    base.py
    models/
  schemas/
  services/
  repositories/
  workers/
  middleware/
```

## 4. API design rules

1. Use `/api/v1` prefix for all versioned APIs.
2. Keep routers small and domain-specific.
3. Keep business logic out of route functions.
4. Use Pydantic schemas for request and response models.
5. Use consistent response and error formats.
6. Public widget APIs must be separated from authenticated dashboard APIs.

## 5. Service layer rules

Service classes or functions own business logic.

Routes should:

- Validate input
- Resolve dependencies
- Call services
- Return schemas

Routes should not:

- Perform complex business rules
- Directly build RAG prompts
- Directly perform vector search
- Directly process uploaded files synchronously

## 6. Repository layer rules

Database access should be isolated in repository modules where practical.

Repository functions must require tenant context for tenant-scoped entities.

Example rule:

```text
Never fetch a document by document_id alone. Fetch by workspace_id and document_id.
```

## 7. Tenant isolation rules

Every tenant-scoped backend operation must resolve one of:

- organisation_id
- workspace_id

The service must verify the current user or public key has access to that scope.

## 8. Error handling

Use clear error categories:

- validation_error
- authentication_error
- authorization_error
- not_found
- conflict
- rate_limited
- processing_error
- external_provider_error
- internal_error

Do not expose internal stack traces in API responses.

## 9. Configuration rules

Configuration must be loaded from environment variables or local config files.

Do not hardcode:

- Database URLs
- API keys
- Storage credentials
- Model provider keys
- Secret values

## 10. Testing rules

Minimum backend tests:

- Health endpoint
- System info endpoint
- Tenant isolation tests
- Permission tests
- Document upload validation tests
- Safe fallback tests for chat

## 11. Dependency rules

Dependencies must be minimal and justified.

Before adding a major dependency, ask:

1. Is it required for MVP?
2. Can standard library or existing dependency do this?
3. Does it increase operational complexity?
4. Does it require an ADR?

## 12. Immediate backend foundation target

TASK-002 should produce:

- Modular FastAPI app
- Config module
- API v1 router
- System router
- Health endpoint
- Test structure
- Minimal requirements

Do not implement database, auth, RAG, or tenant logic in TASK-002.
