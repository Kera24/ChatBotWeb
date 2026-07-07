# Security Rules

Primary source: `docs/06_Security/01_Security_and_RBAC_Model.md`

Related sources:

- `docs/03_AI/01_RAG_Architecture.md`
- `implementation-pack/README.md`

## Core principles

- Tenant isolation is mandatory.
- Least privilege by default.
- Public widget access must be restricted and rate-limited.
- Administrative actions must be audited.
- AI retrieval must never cross organisation or workspace boundaries.
- Avoid collecting unnecessary personal data.
- Fail safely when permission or tenant context is unclear.

## No secrets

Never commit:

- API keys
- Service-role keys
- JWT secrets
- Database passwords
- OAuth secrets
- Client credentials
- Real client documents
- Real user personal data

Use placeholders in docs and examples.

## Tenant checks

Protected routes must verify:

1. User identity
2. Organisation membership
3. Role permission
4. Workspace access where applicable

Retrieval must filter by:

- organisation_id
- workspace_id
- document status
- chunk status

## Public widget checks

The public workspace key is not a secret. It must be combined with:

- Workspace active status
- Organisation active status
- Allowed domain checks
- Rate limits
- Abuse detection
- Optional captcha or challenge later

## File upload checks

Uploaded documents must validate:

- Supported file type
- Maximum file size
- Safe filename handling
- Tenant-scoped storage location
- Processing status

Archived, expired, failed, deleted, or private documents must not be retrieved for public answers.

## Prompt and RAG security

- Do not expose system prompts.
- Do not include other tenants' context.
- Defend against prompt injection in uploaded documents and user messages.
- Prefer refusal or fallback over ungrounded answers.
