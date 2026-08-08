# Prompt Management Architecture

Prompts are managed as software: draft → version → evaluate → approve → release → observe → compare → roll back. This document is the "why" and "how it fits together"; see the companion docs below for narrower topics.

| Question | Doc |
|---|---|
| Layering, immutability, RBAC, injection-lint caveat | `docs/03_AI/Prompt_Layering_and_Security_Policy.md` |
| Draft → approved → active status machine | `docs/04_Engineering/Prompt_Versioning_Guide.md` |
| Evaluation-gated promotion | `docs/04_Engineering/Prompt_Evaluation_and_Promotion_Policy.md` |
| Controlled experiments (traffic split, kill switch, metrics) | `docs/04_Engineering/Prompt_Experiment_Guide.md` |
| Rollback procedure | `docs/06_Operations/Prompt_Rollback_Runbook.md` |
| Variable schema reference | `docs/03_AI/Prompt_Variable_Reference.md` |
| Future Azure deployment mapping | `docs/02_Architecture/Azure_Prompt_Deployment_Mapping.md` |

## The 8-layer model, and why only 3 are DB-backed

The conceptual layer taxonomy is:

1. Immutable platform safety policy
2. RAG answer policy
3. Grounding/citation requirements
4. Assistant persona and tone
5. Organisation-specific guidance
6. Retrieved evidence wrapper (runtime-injected, never a template)
7. User question (runtime-injected, never a template)
8. Structured output schema

Layers 1+2+3+8 are **consolidated into a single `platform_core` `PromptTemplate`** (`app.db.models.prompt.LAYER_PLATFORM_CORE`). They are always authored/approved by the same actor (a super admin) and always evaluated together — versioning them independently would let two immutable layers drift into an untested combination in production (a candidate change to "citation requirements" could go live without ever having been evaluated against whatever "structured output schema" version happened to be active that week). Layers 4 and 5 (`LAYER_ASSISTANT_PERSONA_TONE`, `LAYER_ORGANISATION_GUIDANCE`) are workspace-scoped and independently versioned, since they're lower blast radius and naturally iterate on their own schedule. Layers 6/7 are documented here for completeness but are never stored as templates — they're the `{context}`/`{question}` variables threaded in at request time.

## Data model

`app.db.models.prompt`: `PromptTemplate` (one row per layer per scope; platform-scoped rows have `organisation_id`/`workspace_id` both `NULL`) → `PromptVersion` (immutable once created; `status` moves through the state machine in the Versioning Guide) → `PromptDeployment` (the currently-active, and previous, version for one scope+layer — platform-wide, or one workspace/widget) and `PromptExperiment` (a control-vs-candidate A/B test for one widget+layer) → `PromptAuditEvent` (append-only trail for every mutating action, with before/after JSON snapshots).

Platform-scoped rows (`organisation_id IS NULL`) are the first intentionally-NULL tenant columns in this codebase — the blanket "every query filters organisation_id AND workspace_id" rule does not apply verbatim here. `app.repositories.prompt_repository`'s read functions use an explicit `(org=:org AND ws=:ws) OR (org IS NULL AND ws IS NULL)` clause instead. "One active deployment per scope+layer" is enforced in the repository layer, not a DB constraint, because SQL `UNIQUE` treats `NULL` values as distinct from each other.

## Rendering bridge: how a DB-backed version actually gets used

`app.ai.prompt_registry.PromptRegistry`/`AICoreService`/`AICoreGenerateInput` are **unchanged** as the permanent default — a workspace/widget with zero prompt-management activity behaves identically to before this feature existed, byte for byte.

`app.prompts.resolution.resolve_composite_prompt()` is the new, entirely additive path: given an organisation/workspace/widget, it looks up whichever layers have an active `PromptDeployment` (a single cached query per scope, TTL 30s, invalidated on every deploy/rollback), applies any live `PromptExperiment`'s arm assignment, renders each layer's content (validating declared variables via the same `Formatter()`-based allow-list technique `app.ai.prompt_registry` already used), and returns a `RenderedPrompt` — the exact shape `PromptRegistry.render()` already produces. `AICoreGenerateInput.override_rendered_prompt` (a new trailing-optional field) carries this into `AICoreService.generate()`, which uses it in place of `self.prompt_registry.render(...)` when present. Everything downstream (accounting, `AIRequest`, trace recording) is unaffected since the shape matches exactly.

`resolve_composite_prompt()` returns `None` when nothing is configured for a scope (organic fallback to the code default) — this is the normal, expected dormant state, not an error. It raises when it cannot honour an explicitly-requested `prompt_version_override_id` (see the fail-open/fail-loud split below).

## Composite identity

The legacy scalar `prompt_key`/`prompt_version`/`prompt_hash` triple (non-nullable on `AIRequest`/`AIResponse`) is still populated for composite renders: `prompt_key` stays `"grounded_rag_answer"`, `prompt_version` becomes a synthesized label like `"core:v3+persona:v2+guidance:v1"`, `prompt_hash` is a sha256 over the ordered per-layer checksums. `ChatMessage.prompt_version` (an `Integer` column, populated via `_prompt_version_to_int`'s digit-scrape) stores `NULL` for composite-rendered messages — it cannot represent a composite label, and this is accepted, documented behaviour, not a bug. The **structured, authoritative** record is `AIModelCallTrace.resolved_layer_version_ids` (a new JSON column: `{layer: version_id}`), added alongside three other new trailing-nullable columns on that table: `prompt_version_id` (the `platform_core` layer's resolved version — a quick-filter FK), `experiment_id`, `experiment_arm`.

## Fail-open vs. fail-loud

`app.ai.rag_orchestrator.RAGOrchestrator.answer()` wraps the `resolve_composite_prompt()` call: for organic production/dashboard/widget traffic (`prompt_version_override_id` unset) it catches any exception, falls back to the default code-registered prompt, and records the `prompt_construction` trace stage as `status="degraded", reason_code="prompt_resolution_fallback"` — observable, never silent. When the request carries an explicit `prompt_version_override_id` (only ever set by `app.evaluation.prompt_promotion_gate` / `app.evaluation.engine`, i.e. an evaluation/gate context), the exception is allowed to propagate — correctness matters more than availability there, since the entire point of a gate run is to prove one specific candidate behaves correctly. The gate additionally asserts, post-run, that the resulting `EvaluationRun.prompt_version_id` actually matches the requested candidate id, and raises `PromptGateIntegrityError` if not.

## Known, pre-existing drift not touched by this work

`app.services.prompt_assembly.SYSTEM_PROMPT_TEMPLATE` (used only by the preview-only `POST /{workspace_id}/retrieval/prompt` endpoint in `app.api.v1.workspaces`) is a second, independently-maintained system prompt that predates this feature and has always been textually different from the live `grounded_rag_answer` prompt. Repointing that endpoint at the new composite-rendering bridge was considered and **deliberately not done** — `apps/api/tests/test_prompt_assembly_api.py` has seven passing tests asserting that endpoint's exact current wording and response shape, and changing it would break real, deliberate test coverage for no functional benefit (the endpoint is preview-only, never in the live answer path). The new composite-aware preview lives at a separate, additively-named endpoint instead: `GET /{workspace_id}/prompts/preview`. This is a known limitation to flag, not a regression to fix silently.
