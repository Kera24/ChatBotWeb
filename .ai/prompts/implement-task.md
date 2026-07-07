# Implement Task Prompt

Use this prompt when asking Codex or another AI agent to implement an approved task.

```text
Read `.ai/PROJECT_CONTEXT.md`, `.ai/CURRENT_SPRINT.md`, and the relevant `.ai/agents/` and `.ai/context/` files first.

Task:
[paste task ID, title, and link]

Goal:
[state the implementation goal]

Scope:
- [files or modules allowed]
- [behavior to implement]

Out of scope:
- No unrelated features
- No major dependencies without approval
- No architecture changes unless listed
- No secrets

Required checks:
- Tenant isolation impact
- Security impact
- RAG/source-grounding impact if applicable
- MVP-scope impact
- Tests to run

After implementation, summarise files changed, tests run, risks, and follow-up tasks.
```
