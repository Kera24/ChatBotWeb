# Security and RBAC Model

Version: 0.1
Status: Draft

## 1. Purpose

Define the minimum security and role-based access model for the ChatBotWeb / Yoranix AI Platform MVP.

The platform handles client knowledge, public chatbot traffic, uploaded files, and AI-generated responses. Security must be designed from the beginning.

## 2. Security principles

1. Tenant isolation is mandatory.
2. Least privilege by default.
3. Public widget access must be restricted and rate-limited.
4. Administrative actions must be audited.
5. AI retrieval must never cross organisation or workspace boundaries.
6. The platform should avoid collecting unnecessary personal data.
7. Fail safely when permission or tenant context is unclear.

## 3. Tenant model

The hierarchy is:

```text
Platform
  Organisation
    Workspace
      Documents
      Chunks
      Chat Sessions
      Widget Settings
      Analytics
```

## 4. Roles

### super_admin

Platform operator with access to all organisations.

### org_owner

Client-side owner of an organisation.

### client_admin

Client staff member who manages workspaces, knowledge, chatbot settings, and analytics.

### contributor

Client staff member who can upload or edit knowledge within allowed scope.

### viewer

Client staff member who can view data but not modify settings or knowledge.

## 5. Permission matrix

| Capability | super_admin | org_owner | client_admin | contributor | viewer |
|---|---:|---:|---:|---:|---:|
| View all organisations | Yes | No | No | No | No |
| Create organisation | Yes | No | No | No | No |
| Deactivate organisation | Yes | No | No | No | No |
| Manage own organisation | Yes | Yes | No | No | No |
| Manage users | Yes | Yes | Yes | No | No |
| Manage workspace settings | Yes | Yes | Yes | No | No |
| Upload documents | Yes | Yes | Yes | Yes | No |
| Archive documents | Yes | Yes | Yes | Limited | No |
| Delete documents | Yes | Yes | Yes | No | No |
| View chat history | Yes | Yes | Yes | No | Yes |
| View analytics | Yes | Yes | Yes | No | Yes |
| View audit logs | Yes | Yes | Yes | No | No |

## 6. Authentication requirements

Dashboard access must require authenticated sessions.

The authentication provider may be selected later, but the application must abstract authentication so the provider can change.

The system must store only required user profile information.

## 7. Authorisation requirements

All protected routes must check:

1. User identity
2. Organisation membership
3. Role permission
4. Workspace access where applicable

If any check fails, the request must be rejected.

## 8. Public widget security

The public widget uses a public workspace key.

The public key is not a secret. It identifies the workspace but must be combined with:

- Workspace active status
- Organisation active status
- Allowed domain checks
- Rate limits
- Abuse detection
- Optional captcha or challenge in future

## 9. Document security

Uploaded documents must be validated for:

- Supported file type
- Maximum file size
- Safe filename handling
- Storage location
- Processing status

Documents must be scoped to organisation and workspace.

Archived, expired, failed, or deleted documents must not be used for retrieval.

## 10. RAG security

Retrieval queries must always filter by:

- organisation_id
- workspace_id
- document status
- chunk status

The answer generation prompt must not include documents from other tenants.

The system must not expose hidden system prompts to public users.

## 11. Audit logging

Audit logs must capture:

- Actor
- Action
- Organisation
- Workspace
- Entity type
- Entity ID
- Timestamp
- Relevant before and after state when practical

Events to audit:

- Organisation created or deactivated
- Workspace created or changed
- User invited or role changed
- Document uploaded
- Document archived or deleted
- Widget settings changed
- Knowledge source changed

## 12. Data privacy

The platform should avoid collecting unnecessary personal information from public chatbot users.

If contact capture is added, the UI must make clear what data is collected and why.

## 13. Rate limiting

Rate limits should apply to:

- Public widget config requests
- Public chat session creation
- Public chat messages
- Document uploads
- AI-heavy dashboard test requests

Rate limits should be configurable per organisation or plan in future.

## 14. Security risks

- Cross-tenant data leakage
- Prompt injection through uploaded documents
- Prompt injection through user messages
- Public widget abuse
- Expired knowledge being retrieved
- Insecure file upload handling
- Excessive AI cost from automated traffic

## 15. MVP security checklist

- Auth required for dashboard
- Role checks on protected routes
- Tenant filtering in all queries
- Tenant filtering in all vector retrieval
- Public widget rate limiting
- File type validation
- Audit logs for admin actions
- Safe fallback for unknown answers
- No archived or expired documents in retrieval
