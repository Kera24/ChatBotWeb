# Generate Tests Prompt

Use this prompt to add or improve tests.

```text
Read `.ai/PROJECT_CONTEXT.md`, `.ai/context/coding-standards.md`, and `.ai/context/security-rules.md`.

Add focused tests for:
[describe behavior]

Prioritise:
- Tenant isolation
- Permission checks
- Public endpoint safety
- RAG fallback and citation behavior
- Document lifecycle retrieval rules
- Error handling
- Accessibility for UI where practical

Do not add unrelated test infrastructure unless required.

After implementation, summarise tests added, commands run, and remaining gaps.
```
