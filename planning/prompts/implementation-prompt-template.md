# Implementation Prompt Template

Use this prompt when asking Codex, Cursor, Claude Code, or another coding agent to implement a task.

```text
You are working in the ChatBotWeb / Yoranix AI Platform repository.

This is a multi-tenant AI knowledge platform for RAG chatbots and future AI agents. It is not a one-off chatbot demo.

Before coding, read:

- README.md
- docs/README.md
- docs/07_Roadmap/01_MVP_Implementation_Plan.md
- docs/02_Architecture/01_System_Architecture.md
- docs/06_Security/01_Security_and_RBAC_Model.md
- planning/agents/README.md
- <TASK_FILE>

Your task:

<TASK_SUMMARY>

Rules:

1. Keep MVP scope tight.
2. Preserve tenant isolation in all designs.
3. Do not add unrelated features.
4. Do not commit secrets.
5. Add tests where requested.
6. Update documentation if behaviour or structure changes.
7. Prefer simple, maintainable code over clever abstractions.

Deliverables:

- Implement the requested files and code.
- Explain what changed.
- List tests run.
- List any assumptions or follow-up tasks.
```
