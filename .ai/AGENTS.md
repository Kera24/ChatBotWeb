# Agent Operating Model

Use these briefs to keep Codex and future AI coding agents aligned.

## Required session sequence

1. Read `.ai/PROJECT_CONTEXT.md`.
2. Read `.ai/CURRENT_SPRINT.md`.
3. Select the role brief from `.ai/agents/`.
4. Read the relevant `.ai/context/` file.
5. Read linked source docs, planning tasks, and implementation-pack standards.

## Specialist agents

- Backend agent: `.ai/agents/backend-agent.md`
- Frontend agent: `.ai/agents/frontend-agent.md`
- AI/RAG agent: `.ai/agents/ai-rag-agent.md`
- Database agent: `.ai/agents/database-agent.md`
- Security agent: `.ai/agents/security-agent.md`
- DevOps agent: `.ai/agents/devops-agent.md`
- QA agent: `.ai/agents/qa-agent.md`
- Design agent: `.ai/agents/design-agent.md`

## Coordination rules

- Backend, database, AI/RAG, analytics, and widget work must involve tenant-isolation review.
- Public endpoint work must involve security review.
- RAG work must involve grounding, citation, and failure-behavior review.
- UI work must involve design review and accessibility review.
- Deployment work must involve secrets and environment review.
- Any major dependency or architecture change requires documentation and likely an ADR.

## Handoff format

When an agent completes work, report:

- Task and source links used
- Files changed
- Behavior changed
- Tests run
- Tenant isolation impact
- Security impact
- RAG/source-grounding impact
- MVP-scope impact
- Follow-up risks
