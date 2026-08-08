# Agent Framework

## Purpose

Support agentic behavior (multi-step tool use, assistant-to-assistant delegation, autonomous multi-turn task execution) beyond the current single-turn retrieve-and-answer model, and support additional channels (Slack/Teams/voice) as a generalization of the current widget-only delivery.

## Current limitation

`docs/architecture/retrieval.md`/`docs/engineering/rag-pipeline.md` — the RAG pipeline answers one question per request with no tool use, no multi-step planning, and no delegation between assistants; `docs/engineering/assistant-architecture.md` — only one channel (the website widget) is supported.

## Why postponed

This is the highest-complexity, most speculative item in the roadmap — it depends on nearly everything else (memory, hybrid retrieval, model routing, observability at maturity) being in place first, and no current product requirement demands agentic behavior. Building it early would mean designing against imagined rather than real use cases.

## Dependencies

- `docs/future/MemoryV2.md` (agentic multi-step behavior needs conversation state).
- `docs/future/ModelRouting.md` (different steps of an agentic task may warrant different models).
- Mature observability (`docs/architecture/observability.md`) and evaluation (`docs/engineering/evaluation.md`) — agentic behavior is harder to evaluate than single-turn Q&A and needs the strongest possible measurement foundation before being trusted.
- A second delivery channel requirement (`docs/engineering/system-architecture.md`'s future item) if the "additional channel" half of this is pursued, via a new `app.access.channels.*` adapter.

## Implementation phases

1. Second channel first (lower risk, reuses the existing single-turn `RAGOrchestrator` core unchanged) — proves the "one core, multiple channels" model before adding agentic complexity.
2. Tool-use within a single turn (assistant can invoke a defined tool, e.g. a lookup, as part of answering one question) as the smallest agentic increment.
3. Multi-step planning/execution across turns, built on `docs/future/MemoryV2.md`.
4. Assistant-to-assistant delegation, only if a real use case emerges — explicitly out of scope for `docs/engineering/assistant-architecture.md` today and would need its own ADR to reverse that.

## Technical design

Deliberately unspecified beyond phase 1 — this is the least mature item in the entire roadmap and any concrete technical design before the dependencies above are in place would be speculative.

## Evaluation plan

Each phase needs its own evaluation case set (tool-use correctness, multi-step task completion rate) distinct from the existing single-turn answer-quality cases — agentic evaluation is a different measurement problem, not an extension of the existing one.

## Rollback strategy

Phase 1 (new channel) is purely additive. Later agentic phases should ship behind assistant-level opt-in flags, never as a default behavior change to existing single-turn assistants.

## Success metrics

Not yet defined beyond phase 1 (successful second-channel delivery with no regression to the core pipeline) — later-phase metrics should be defined when those phases are actually scoped, not speculatively now.
