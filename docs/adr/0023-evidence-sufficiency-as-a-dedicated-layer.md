# ADR-0023: Evidence Sufficiency as a Dedicated Guardrail Layer

Status: Accepted
Date: 2026-08-07

## Context

Retrieval can return chunks that are topically related to a question without actually containing the specific fact needed to answer it (e.g. a document mentions "pricing" broadly but not the specific figure asked about). A naive grounding check that only verifies "the answer cites a real chunk" would pass in this case even though the answer isn't truly supported. The team needed to decide whether this check belongs inside citation verification or as its own layer.

## Decision

Implement evidence sufficiency as its own guardrail layer (Layer A+B, `app.ai.guardrails.evidence_sufficiency.verify_evidence_sufficiency()`), distinct from citation policy (Layer F, `app.ai.guardrails.citation_policy.verify_citations()`).

## Alternatives

- **Fold sufficiency checking into citation policy** — rejected: citation policy verifies structural/scope correctness (citations stay within the allowed document set); evidence sufficiency verifies semantic correctness (the evidence actually supports the specific claim). Conflating them would make either check harder to reason about and test in isolation.
- **Rely on output-safety layer (G+H) to catch ungrounded answers post-hoc** — rejected: output safety runs after generation and is oriented toward safety/leakage, not fact-support; catching insufficiency before generation is cheaper (no wasted provider call) and more precise than trying to detect it after the fact from generated text alone.

## Tradeoffs

- Gains: a testable, independently gradeable check for "does the evidence actually support this specific question," which is the check most directly related to unsupported-answer/grounding-failure signals (see `docs/06_Operations`'s AI Metrics Dictionary terminology rules — never called "hallucination rate").
- Costs: one more pipeline stage to instrument, trace, and maintain test coverage for.

## Consequences

- Evidence sufficiency runs before generation, so it can prevent a wasted provider call the same way input policy does.
- Observability traces this stage explicitly (`ai_guardrail_traces`, layer `A+B`) — see `docs/architecture/observability.md`.

## Future reconsideration triggers

If the `grounding.py` module (`app.ai.guardrails.grounding`, not currently wired into the live pipeline — see `docs/architecture/guardrails.md`) is wired in, its relationship to evidence sufficiency must be explicitly defined (complementary layer vs. replacement) rather than left ambiguous.
