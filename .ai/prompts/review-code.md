# Review Code Prompt

Use this prompt for code review.

```text
Read `.ai/PROJECT_CONTEXT.md` and the relevant `.ai/context/` files.

Review the changes as a senior engineer. Prioritise findings over summary.

Focus on:
- Correctness
- Tenant isolation
- RBAC and permission checks
- RAG source grounding if applicable
- Security and no secrets
- MVP scope
- Error handling
- Test coverage
- Accessibility for UI changes
- Expressionism alignment for UI changes

Return:
1. Findings ordered by severity with file and line references.
2. Open questions or assumptions.
3. Brief change summary only after findings.
4. Tests reviewed or missing.
```
