# AI Lifecycles

Request-flow and data lifecycles across the AI system. Companion document `docs/engineering/ai-system-design.md` covers provider/model strategy.

## Prompt lifecycle

`draft → testing → active → deprecated → retired` (ADR 0003). A version's template is immutable once active — changes require a new version, never an in-place edit. Every execution records `prompt_key`/`prompt_version`/`prompt_hash` on the `ChatMessage` row. See `docs/engineering/prompt-versioning.md`.

## Context assembly

`app.services.prompt_assembly.assemble_grounded_prompt()`, called from `AICoreService.generate()`, combines the user question, retrieved/sanitized evidence chunks (post document-sanitizer, Layer E), and the active prompt template into the final generation input. Currently stateless per-request — no prior-turn context is assembled in (see Memory lifecycle below). See `docs/architecture/retrieval.md`.

## Retrieval lifecycle

Query embedding → vector search (`app.services.vector_search`) → candidate chunks → citation policy (Layer F) → document sanitization (Layer E) → evidence sufficiency (Layer A+B). Each stage is traced individually (`ai_retrieval_traces`, `docs/architecture/observability.md`). Knowledge-scope isolation (`knowledge_scope_json`) is enforced at the vector-search step itself, not filtered after the fact. See `docs/engineering/rag-pipeline.md`.

## Memory lifecycle

**Current**: none — no state carries between questions in the same conversation beyond what's persisted in `ChatMessage` history for display purposes; each `RAGOrchestrator.answer()` call is independent. **Future**: `docs/future/MemoryV2.md` — short-term (recent-turn injection into context assembly) then long-term (cross-conversation, per-tenant-scoped) memory, each requiring its own evaluation and privacy review before shipping.

## Evaluation lifecycle

`EvaluationDataset` → `EvaluationCase` → `EvaluationRun` → `EvaluationResult`. Deterministic scoring (`evaluation/scoring.py`) is launch-gating; model-based grading (`evaluation/graders/`) runs alongside but stays advisory until calibrated. Runs can be triggered against fixed datasets today; `docs/future/EvaluationV2.md` extends this lifecycle to include continuously-sampled production traces. See `docs/architecture/evaluation.md`.

## Guardrail lifecycle

Per-request, guardrail layers A-H execute inline within `RAGOrchestrator.answer()` at fixed points in the pipeline (input policy before retrieval, citation/sanitization/evidence-sufficiency around retrieval, output safety after generation). Every layer's verdict is traced (`ai_guardrail_traces`). A blocking verdict at any layer routes to `_persist_fallback()`, never a silent drop. See `docs/architecture/guardrails.md`.

## Production feedback lifecycle

**Current**: production behavior is visible via AI observability traces (`docs/architecture/observability.md`) and the `/observability` dashboard, but there is no automated loop feeding that signal back into evaluation case sets or prompt/guardrail tuning — that connection is manual today (an engineer reviews traces, then decides what to change). **Future**: `docs/future/EvaluationV2.md`'s continuous evaluation and `docs/future/GuardrailsV2.md`'s observability-driven new-layer process both formalize this into a closed loop: production signal → case set / guardrail proposal → evaluation → (if justified) shipped change → new production signal.

## How these lifecycles connect

A single request touches all seven in order: a prompt version is selected (prompt lifecycle) → context is assembled from a retrieval pass (retrieval lifecycle, context assembly) → guardrails gate the request at multiple points (guardrail lifecycle) → the result is persisted and traced, becoming input to both the evaluation lifecycle (if sampled) and the production feedback lifecycle (if reviewed). Memory lifecycle, once built, would inject into context assembly from the same persisted history the production feedback lifecycle also reads.
