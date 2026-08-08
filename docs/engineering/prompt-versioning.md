# Prompt Versioning — Current / Future / Out of Scope

## Current

Prompts are stored as immutable versioned "logical prompt definitions" with lifecycle states `draft → testing → active → deprecated → retired` (ADR 0003, Accepted). Once a version is active/used, its template content cannot be edited in place — a change requires a new version. Every execution records `prompt_key`/`prompt_version`/`prompt_hash` on the `ChatMessage` row (`docs/engineering/conversation-lifecycle.md`), so any historical answer can be traced back to the exact prompt text that produced it. Assembly happens in `apps/api/app/services/prompt_assembly.py` (`assemble_grounded_prompt()`), called from `AICoreService.generate()` inside the RAG pipeline (`docs/architecture/retrieval.md`).

## Future

- A/B or shadow-testing between prompt versions before promoting `testing → active` — see `docs/future/PromptOptimisation.md`.
- Automated prompt regression detection tied to evaluation runs (flag a new active version that regresses grader scores) — see `docs/future/EvaluationV2.md`.

## Out of scope (not planned)

- Editing an active prompt version's template text in place — this would break the hash-based traceability the `prompt_hash` field exists to guarantee; always version instead.
