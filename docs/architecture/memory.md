# Conversation Memory

**There is no multi-turn memory system today.** Every question is answered independently of prior turns in the same conversation. This document exists so that future work doesn't assume memory exists, and so a future "add conversation memory" task has an accurate starting point.

## What actually happens

- `RAGOrchestrator.answer()` builds the generation prompt from exactly two variables: `{"question": request.query, "context": context}`, where `context` is only the chunks retrieved *for this specific query* (see `retrieval.md`).
- No prior `ChatMessage` rows from the same `conversation_id` are fetched or injected into the prompt at generation time.
- `conversation_id` is threaded through the orchestrator and *is* used to persist the full transcript (`app.services.conversation`) and to group messages/citations in the dashboard's Conversations view — but this is write-only from the generation pipeline's perspective. The transcript is for humans (and evaluation/observability tooling) to read, not for the model to read back.

## Implication for related features

- The evaluation framework (`evaluation.md`) scores each case independently; there is no multi-turn evaluation category today.
- The AI observability trace model (`observability.md`) records `conversation_id` on each trace for correlation, but each trace is still a single independent request.
- A user asking a follow-up question that depends on earlier context ("what about the second one?") will not currently be answered correctly — the assistant has no way to know what "the second one" refers to.

## If asked to add conversation memory

This would be new work, not a bug fix. At minimum it would need: a bounded strategy for how much prior context to include (full transcript doesn't scale), a decision on whether summarization is needed, and careful interaction with the guardrail chain (older turns could themselves have been guardrail-blocked or contain injected instructions — Layer E's document sanitization currently only covers retrieved *document* content, not prior conversation turns). Treat this as a design decision requiring explicit user sign-off, not something to bolt on inside an unrelated task.
