# Query Rewrite

## Purpose

Rewrite/expand user queries (resolve pronouns from conversation context, expand abbreviations, generate multiple query variants) before retrieval, to improve recall for poorly-phrased or context-dependent questions.

## Current limitation

The raw user question is embedded and searched as-is (`docs/architecture/retrieval.md`); a question like "what about the second one" has no context to resolve against, and ambiguous phrasing isn't expanded before retrieval.

## Why postponed

Meaningfully depends on `docs/future/MemoryV2.md` for conversation-context-dependent rewrites (pronoun resolution needs prior turns); context-free rewriting (expansion/clarification) alone has limited value and unproven benefit without evaluation data showing it helps.

## Dependencies

- `docs/future/MemoryV2.md` (short-term memory) for context-dependent rewrites.
- A real generation provider capable of cheap, fast rewrite calls without materially increasing end-to-end latency.

## Implementation phases

1. Context-free query normalization/expansion (abbreviation expansion, spelling correction) as a low-risk first step.
2. Context-dependent rewrite (pronoun/reference resolution using recent conversation turns) once `docs/future/MemoryV2.md` ships.
3. Multi-query expansion (generate several query variants, retrieve for each, merge) as a higher-cost, higher-recall option evaluated separately.

## Technical design

New pre-retrieval step in `RAGOrchestrator.answer()`, additive before `assemble_retrieval_context()` — input policy (guardrail Layer C+D) still evaluates the *original* user input, not the rewritten query, so guardrail behavior doesn't change.

## Evaluation plan

Recall improvement on a case set specifically constructed with ambiguous/context-dependent/poorly-phrased questions; verify no latency regression makes the tradeoff not worth it.

## Rollback strategy

Flag-gated pre-retrieval step; disabling reverts to using the raw user question, no schema impact.

## Success metrics

Reduced fallback/evidence-insufficient rate specifically on ambiguous or context-dependent questions.
