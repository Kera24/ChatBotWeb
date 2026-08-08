# Future Roadmap (Architecture-Relevant Items Only)

This is not a product roadmap (see `docs/07_Roadmap/01_MVP_Implementation_Plan.md` for that) — it's a list of known architectural gaps and likely next steps, so future work starts from an accurate picture instead of rediscovering these each time.

## Known gaps, in rough likely-priority order

1. **Live AI provider.** Only `MockAIProvider` exists (`retrieval.md`). Adding a real provider (OpenAI/Anthropic/Azure OpenAI) means implementing `AIProvider`, registering it in `ProviderRegistry`/`ModelRegistry`, and setting real `input_cost_per_million_tokens`/`output_cost_per_million_tokens` so cost accounting (`observability.md`) is accurate rather than `$0`.
2. **Email delivery.** Password reset and email verification exist at the data layer but have no email delivery wired up (`authentication.md`). Needed before either flow is real.
3. **Conversation memory.** Explicitly absent today (`memory.md`) — a deliberate, documented gap, not a bug. Needs a bounded-context design before implementation.
4. **Rejected-chunk visibility in AI traces.** `retrieval_context.py` doesn't currently return candidates considered but not selected, so the observability retrieval debugger only shows selected chunks (see `docs/03_AI/AI_Observability_Architecture.md`'s deferred-scope list).
5. **Grounding guardrail wiring.** `app.ai.guardrails.grounding.verify_grounding()` exists but isn't called from the pipeline (`guardrails.md`) — evidence sufficiency currently covers this concern functionally.
6. **AI trace recording on SQLite for evaluation runs.** Currently a no-op there due to a real cross-thread contention issue (`observability.md`'s Limitations). Would need either a different threading model in the evaluation engine or a more sophisticated SQLite-safe write strategy.
7. **`encrypted_full_content` trace retention mode.** Schema/enum exist; real encryption-at-rest needs a KMS/key-management decision (`docs/03_AI/AI_Trace_Data_and_Privacy_Policy.md`).
8. **Materialized cost/metrics rollups.** Currently computed on-read via SQL `GROUP BY` — fine at controlled-pilot scale, will need a rollup table if traffic grows meaningfully (see `docs/future/ObservabilityV2.md` and `docs/adr/0024-observability-before-scaling.md`).

## Channel expansion (long-term platform vision)

Per `docs/CONSTITUTION.md`'s "Long-term platform vision": the widget is the first channel, not the only one. Adding a second channel (Slack/Teams integration, internal staff assistant, voice) should follow the existing `app.access.channels.widget` adapter pattern rather than forking the RAG/guardrail/evaluation/observability core — those layers are already channel-agnostic by design.

## Deployment path

VPS (now) → optional VPS observability stack (now, opt-in) → Azure (future, infrastructure kept live but not provisioned) — see `deployment.md` and `docs/02_Architecture/Azure_Monitor_Application_Insights_Mapping.md`.

## Dark mode

CSS `.dark` rules exist throughout `globals.css` but are currently dormant — no code path adds a `dark` class or `data-theme` attribute anywhere in `apps/web`. A real dark-mode toggle would need a theme-state mechanism (context + `localStorage`, most likely) wired to the `<html>`/`<body>` element; see `docs/design/design-system.md`.

## Before starting any of the above

Re-check this list against the actual current codebase first — it may be stale by the time you read it. Grep for the specific claim (e.g. "does `MockAIProvider` still exist," "is `verify_grounding` still unwired") rather than trusting this document blindly, per `CLAUDE.md`'s evidence-driven-engineering rule.
