# Guardrail Architecture

All guardrails live in `apps/api/app/ai/guardrails/`, wired into `RAGOrchestrator.answer()` (`retrieval.md`). Each layer has one narrow job. **Never remove or weaken a layer to make a feature "work" — fix the layer's logic explicitly and explain why, or route around it only with explicit instruction.**

## The layer taxonomy (A through H)

| Layer | Module | Function | Runs when | Job |
|---|---|---|---|---|
| C+D | `input_policy.py` | `evaluate_input_policy()` | Before retrieval | Capability/intent boundaries and direct prompt-injection defence. A blocked request never reaches retrieval or the AI provider. |
| — | (retrieval itself) | `assemble_retrieval_context()` | — | Not a guardrail, but the knowledge-scope boundary is enforced here (see `retrieval.md`'s "Knowledge scoping"). |
| F | `citation_policy.py` | `verify_citations()` | After retrieval | Defence-in-depth assertion that citations stay within the allowed document scope — should essentially never fire given retrieval's own scoping; if it does, treat as a priority investigation into retrieval itself. |
| E | `document_sanitizer.py` | `sanitise_evidence_content()` | After retrieval, before context assembly | Strips injected-instruction-style text from retrieved document content — the generation model never sees an attempted prompt-injection override embedded in a document. |
| A+B | `evidence_sufficiency.py` | `verify_evidence_sufficiency()` | After sanitization | Does the evidence support the *specific* fact asked, not just the general topic — multi-signal (requested-attribute/value-type extraction, sentence-level proximity, retrieval-confidence-based domain relevance). Has documented, honest limitations in its own module. |
| — | `grounding.py` | `verify_grounding()` | **Not wired into the live pipeline** | Exists but unused. Do not assume it runs. If asked to wire it in, that's new work, not a bug fix. |
| G+H | `output_safety.py` | `check_output_safety()` | After generation, before persistence/return | Markup neutralization + secret/prompt-leakage pattern detection. Never persist or return raw generated text without this check. |
| — | `reason_codes.py` | `GuardrailReasonCode` enum | — | Shared reason-code vocabulary across all layers — reuse existing codes before adding a new one. |

## Reading a guardrail decision

Every layer returns a verdict object (`InputPolicyVerdict`, `CitationPolicyVerdict`, etc.) with at minimum a pass/fail boolean and a `reason_code`. A block routes to `RAGOrchestrator._persist_fallback()` with that reason code attached to the persisted message's metadata (never as a new `answer_state` value — `answer_state` stays one of `answered`/`fallback`/`failed` for API/dashboard compatibility).

## How this connects to observability and evaluation

- Every layer's verdict is captured as an `AIGuardrailTrace` row (`observability.md`) — layer, verdict, blocked, reason_code, safe (non-content) detail.
- The evaluation framework (`evaluation.md`) exercises these layers directly via real `RAGOrchestrator` calls, including dedicated isolation-category cases that assert guardrails correctly reject cross-tenant attempts.

## Adding a new guardrail layer

1. New module in `app/ai/guardrails/`, following the existing verdict-object + reason-code shape.
2. Wire it into `RAGOrchestrator.answer()` at the correct point in the pipeline (see `retrieval.md`'s stage order) — additive only, don't restructure existing stages.
3. Add reason codes to `reason_codes.py` rather than inventing ad hoc strings.
4. Add an `AIGuardrailTrace`/`AITraceStage` recording call following the existing pattern for the other layers.
5. Add test coverage in `apps/api/tests/test_rag_orchestrator.py` (or a dedicated guardrail test file) and re-run the full suite plus `eval:test`.

## Rules

- Guardrails are security/trust controls, not just quality nudges — treat a proposal to loosen one with the same scrutiny as a proposal to loosen RBAC.
- If a guardrail produces a false positive on a legitimate case, fix the guardrail's detection logic with a reproducible test case — never special-case around it in the orchestrator.

## Relationship to prompt management

Versioned/customer-editable prompt content (`docs/architecture/prompts.md`) is layered *underneath* these guardrails, not a substitute for any of them — no guardrail layer was added, removed, or modified to support prompt management. In particular, none of the 8 layers inspect system-prompt content itself; the mitigation against a compromised or malicious customer-authored prompt layer is structural (subordination language in the platform-immutable layer) plus the unmodified output-safety guardrail (G+H), which still runs on every generation regardless of which prompt layers were composed in. See `docs/03_AI/Prompt_Layering_and_Security_Policy.md` for the full reasoning.
