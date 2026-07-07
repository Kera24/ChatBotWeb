# API Specification

Version: 0.1
Status: Draft

## 1. Purpose

Define the initial API surface for the ChatBotWeb / Yoranix AI Platform MVP.

The API must support dashboard operations, document management, chatbot messaging, analytics, and public widget access.

## 2. API style

Initial API style: REST.

Future options:

- WebSocket streaming for chat responses
- GraphQL for complex dashboard querying
- Public SDK for partner integrations

## 3. Base paths

```text
/api/v1/admin
/api/v1/orgs
/api/v1/workspaces
/api/v1/knowledge
/api/v1/chat
/api/v1/widget
/api/v1/analytics
/api/v1/audit
```

## 4. Authentication model

Dashboard APIs require authenticated user sessions or bearer tokens.

Public widget APIs use a workspace public key and domain validation.

## 5. Common response format

Successful response:

```json
{
  "success": true,
  "data": {},
  "meta": {}
}
```

Error response:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

## 6. Admin APIs

### GET /api/v1/admin/organisations

List organisations.

Required role: super_admin.

### POST /api/v1/admin/organisations

Create organisation.

Required role: super_admin.

Request body:

```json
{
  "name": "Example College",
  "slug": "example-college"
}
```

### PATCH /api/v1/admin/organisations/{organisation_id}

Update organisation.

Required role: super_admin.

### POST /api/v1/admin/organisations/{organisation_id}/deactivate

Deactivate organisation.

Required role: super_admin.

## 7. Workspace APIs

### GET /api/v1/orgs/{organisation_id}/workspaces

List workspaces for organisation.

Required role: org_owner or client_admin.

### POST /api/v1/orgs/{organisation_id}/workspaces

Create workspace.

Required role: org_owner or client_admin.

Request body:

```json
{
  "name": "Admissions Assistant",
  "slug": "admissions"
}
```

### GET /api/v1/workspaces/{workspace_id}

Get workspace details.

### PATCH /api/v1/workspaces/{workspace_id}

Update workspace details.

## 8. Knowledge APIs

### GET /api/v1/workspaces/{workspace_id}/documents

List documents.

### POST /api/v1/workspaces/{workspace_id}/documents

Upload a document.

Content type: multipart/form-data.

Fields:

- file
- title
- category

### GET /api/v1/workspaces/{workspace_id}/documents/{document_id}

Get document details.

### POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/archive

Archive document.

### DELETE /api/v1/workspaces/{workspace_id}/documents/{document_id}

Soft delete document.

### POST /api/v1/workspaces/{workspace_id}/faqs

Create manual FAQ.

Request body:

```json
{
  "question": "When does orientation start?",
  "answer": "Orientation starts on the published date in the current intake schedule.",
  "category": "Admissions"
}
```

## 9. Chat APIs

### POST /api/v1/chat/sessions

Create dashboard test chat session.

Authenticated route.

### POST /api/v1/chat/sessions/{session_id}/messages

Send a message inside an authenticated dashboard test session.

Request body:

```json
{
  "message": "When is the next intake?"
}
```

Response body:

```json
{
  "success": true,
  "data": {
    "answer": "The answer generated from the workspace knowledge base.",
    "answer_state": "answered",
    "citations": []
  }
}
```

## 10. Public widget APIs

### GET /api/v1/widget/config/{public_key}

Return public widget configuration.

Response includes:

- bot_name
- welcome_message
- primary_colour
- logo_url
- suggested_questions

### POST /api/v1/widget/{public_key}/sessions

Create public chat session.

### POST /api/v1/widget/{public_key}/messages

Send public chatbot message.

Request body:

```json
{
  "session_id": "session-id",
  "message": "How do I apply?"
}
```

## 11. Analytics APIs

### GET /api/v1/workspaces/{workspace_id}/analytics/overview

Returns overview metrics.

### GET /api/v1/workspaces/{workspace_id}/analytics/unanswered

Returns unanswered or low-confidence questions.

### GET /api/v1/workspaces/{workspace_id}/analytics/conversations

Returns chat sessions.

## 12. Widget settings APIs

### GET /api/v1/workspaces/{workspace_id}/widget-settings

Get widget settings.

### PATCH /api/v1/workspaces/{workspace_id}/widget-settings

Update widget settings.

Request body:

```json
{
  "bot_name": "Admissions Assistant",
  "welcome_message": "Hi, how can I help?",
  "primary_colour": "blue",
  "suggested_questions": [
    "When is orientation?",
    "How do I apply?"
  ]
}
```

## 13. Audit APIs

### GET /api/v1/workspaces/{workspace_id}/audit-events

Returns audit events for a workspace.

Required role: org_owner or client_admin.

## 14. API security rules

1. Every protected route must validate authentication.
2. Every tenant-scoped route must validate membership.
3. Public widget routes must validate public key and allowed domains.
4. Public chat routes must be rate-limited.
5. Document upload routes must validate file type and size.
6. All admin actions must create audit events.

## 15. Future API additions

- Streaming chat responses
- Website crawler endpoints
- Integration connection APIs
- Billing APIs
- Evaluation APIs
- Agent tool APIs
- Human handover APIs
