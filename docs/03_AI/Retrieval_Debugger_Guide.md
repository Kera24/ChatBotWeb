# Retrieval Debugger Guide

Status: implemented

## Where to find it

`/observability/traces/{traceId}` (dashboard, requires `org_owner`/`client_admin`/`viewer` in the trace's organisation) - the "Retrieval debugger" panel, alongside the request timeline, guardrail outcomes, and model call/cost breakdown.

## What it shows

For the trace's retrieval stage:

- **Rank** - the chunk's position in the ranked result set.
- **Source title** - the document title the chunk came from (safe to show; already visible in citations elsewhere in the product).
- **Similarity score** - the raw cosine-similarity score from `app.services.vector_search`.
- **Selected / Rejected badge** - whether the chunk made it into the final context window sent to the model.
- **Content preview** - only shown when `?include_content=true` is passed **and** the caller has `org_owner`/`client_admin`, and only ever a redacted, truncated (max 500 char) preview - never the raw chunk text. See `AI_Trace_Data_and_Privacy_Policy.md`.

## Reading a trace end-to-end

The debugger is one panel in a larger picture. Read the trace detail page top-to-bottom to reconstruct the full decision:

1. **Summary header** - answer_state, channel, total latency, token count.
2. **Request timeline** - all 14 stages in order, each with status/latency/reason_code. A `blocked` or `error` status here tells you exactly which stage stopped the request (if any) before it reached generation.
3. **Retrieval debugger** - what evidence was available and selected.
4. **Guardrail outcomes** - the A-H layer verdicts (see `AI_Metrics_Dictionary.md`), each with a reason_code when blocked.
5. **Model call & cost breakdown** - provider/model/prompt version, token counts, cost (or "unknown" if unpriced), outcome, and (with content access) redacted prompt/response previews.

## Known scope limit: rejected chunks

Today, the debugger only shows chunks that were **selected** into the context window. `app.services.retrieval_context.assemble_retrieval_context` does not currently return the full candidate list (chunks considered but excluded by the context-budget or top-k cutoff), so there is nothing to render for "rejected" candidates yet. If you need to debug "why wasn't chunk X used," check:

- Whether the assistant's knowledge scope (`knowledge_scope_json`) includes the document at all (a scope exclusion never reaches retrieval).
- The `RETRIEVAL_MIN_SIMILARITY_SCORE` setting - chunks below this score are filtered out by `app.services.vector_search` before ranking, invisible to this trace.
- The `retrieval_limit`/`max_context_chars` request parameters - chunks beyond the top-k or context-character budget are dropped during context assembly, also invisible to this trace today.

Extending `RetrievalContextResult` to carry the full candidate list (with per-candidate rejection reasons) is the natural next step for full rejected-chunk visibility - tracked as a follow-up in `AI_Observability_Architecture.md`'s deferred-scope list.

## Interpreting similarity scores

The bundled `local-mock` embedding provider is a SHA-256 hash with no semantic content - its similarity scores are not meaningful for judging relevance (see `docs/04_Engineering/Evaluation_Task_Specification.md`'s Phase 8 finding, referenced in `RETRIEVAL_MIN_SIMILARITY_SCORE`'s own code comment). Only trust similarity-score-based reasoning in traces produced with a real semantic embedding provider (e.g. `ollama`).
