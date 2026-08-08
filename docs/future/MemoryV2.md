# Memory V2 (Conversation and Long-Term Memory)

## Purpose

Give assistants awareness of prior turns in a conversation (short-term) and, later, recurring per-user/per-workspace context (long-term), instead of answering every question independently.

## Current limitation

`docs/engineering/memory.md` — no multi-turn memory exists; every question is answered from retrieval alone, with no awareness of what was asked or answered earlier in the same conversation.

## Why postponed

Memory changes the shape of the RAG pipeline's context assembly and has real privacy/tenant-isolation implications (what gets remembered, for how long, visible to whom) — it needed the observability and evaluation foundations in place first to measure its effect safely.

## Dependencies

- `docs/architecture/observability.md` (to measure whether memory improves or degrades answer quality).
- `docs/engineering/conversation-lifecycle.md`'s existing `ChatSession`/`ChatMessage` model (memory builds on persisted conversation history, not a new store).

## Implementation phases

1. **Short-term**: inject the last N turns of the current conversation into prompt assembly (`app.services.prompt_assembly`), bounded and redaction-aware.
2. Evaluate short-term memory's effect on answer quality/groundedness before proceeding.
3. **Long-term**: per-user/per-workspace recurring context (preferences, previously-established facts), as a distinct, later phase with its own privacy review.

## Technical design

Short-term: `RAGOrchestrator.answer()` gains an additive context-assembly step reading recent `ChatMessage` rows for the current `ChatSession`, passed into prompt assembly alongside retrieved chunks — retrieval/guardrail logic is unchanged. Long-term: a new store (schema TBD at design time) explicitly scoped at least as tightly as the existing knowledge-scope/tenant-isolation boundary.

## Evaluation plan

A/B conversation-quality evaluation (multi-turn case sets, not just single-question cases) comparing with/without short-term memory; explicit privacy review before any long-term memory design is finalized.

## Rollback strategy

Short-term memory is a prompt-assembly addition, disableable via flag with no schema rollback needed. Long-term memory (once built) needs an explicit data-retention/deletion story before rollback can be considered safe.

## Success metrics

Improved multi-turn conversation coherence/groundedness in evaluation, with no new cross-tenant or cross-conversation data leakage.
