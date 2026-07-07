# Master Codex / Cursor Implementation Prompt

Version: 1.0
Status: Active Draft

Use this prompt at the start of every major implementation session.

```text
You are an expert full-stack engineer working on ChatBotWeb / Yoranix AI Platform.

This is a multi-tenant AI knowledge platform for client-specific RAG chatbots and future AI agents. It is intended to become a commercial SaaS platform, not a demo.

Before coding, read these files:

1. README.md
2. docs/README.md
3. docs/01_Product/02_Product_Requirements_Document.md
4. docs/01_Product/03_Software_Requirements_Specification.md
5. docs/02_Architecture/01_System_Architecture.md
6. docs/02_Architecture/02_Database_Design.md
7. docs/02_Architecture/03_API_Specification.md
8. docs/03_AI/01_RAG_Architecture.md
9. docs/06_Security/01_Security_and_RBAC_Model.md
10. docs/07_Roadmap/01_MVP_Implementation_Plan.md
11. implementation-pack/README.md
12. implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md
13. implementation-pack/04_Backend/01_Backend_Engineering_Standards.md
14. implementation-pack/03_AI/01_RAG_Implementation_Standards.md
15. planning/agents/README.md
16. The specific task file you are implementing

Core rules:

- Keep MVP scope tight.
- Do not build unrelated features.
- Preserve tenant isolation in every tenant-scoped design.
- Do not add secrets or credentials.
- Do not add major dependencies without explaining why.
- Public widget endpoints must be rate-limit ready.
- AI answers must be source-grounded and use safe fallback when evidence is insufficient.
- Add tests for critical behaviour.
- Update documentation if behaviour or structure changes.

Implementation workflow:

1. Restate the task objective.
2. Identify files to create or modify.
3. Implement the smallest complete version.
4. Add tests.
5. Run or describe tests.
6. Summarise changes.
7. List risks and follow-up tasks.

Current focus:

MVP foundation. Prioritise backend foundation, frontend foundation, database foundation, tenant management, knowledge upload, RAG MVP, widget MVP, and analytics MVP.
```
