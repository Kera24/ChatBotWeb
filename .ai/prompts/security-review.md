# Security Review Prompt

Use this prompt for security-sensitive changes.

```text
Read `.ai/PROJECT_CONTEXT.md`, `.ai/context/security-rules.md`, and `docs/06_Security/01_Security_and_RBAC_Model.md`.

Review this change for:
- Cross-tenant data leakage
- Missing tenant filters
- Missing RBAC checks
- Public widget abuse
- Unsafe file upload handling
- Prompt injection
- Secret exposure
- Overly detailed errors
- Missing audit logging
- RAG retrieval of archived, expired, failed, deleted, or private documents

Return findings ordered by severity with exact file and line references.
```
