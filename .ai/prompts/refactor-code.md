# Refactor Code Prompt

Use this prompt for scoped refactoring.

```text
Read `.ai/PROJECT_CONTEXT.md` and relevant `.ai/context/` files.

Refactor only the code required by this task:
[describe scope]

Constraints:
- Preserve behavior unless explicitly changing it.
- Do not introduce new features.
- Do not change architecture without approval.
- Do not add dependencies unless approved.
- Preserve tenant isolation, permissions, and RAG grounding behavior.
- Keep tests passing.

After refactoring, summarise behavior preserved, files changed, tests run, and any risk.
```
