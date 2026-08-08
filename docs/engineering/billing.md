# Billing — Current / Future / Out of Scope

## Current

Stripe subscriptions, 3-tier plan catalog (starter/professional/enterprise), gateway-abstracted (`BillingGateway` Protocol), webhook-driven state sync, always-200 webhook responses. Full detail: `docs/architecture/billing.md`.

## Future

- Usage-based billing tied to AI trace cost data (`ai_model_call_traces` — see `docs/architecture/observability.md`) once a real AI provider makes token costs meaningful (see `docs/future/CostOptimisation.md`).
- Self-serve plan upgrade/downgrade proration UI beyond the current checkout/portal redirect flow.

## Out of scope (not planned)

- Custom/negotiated enterprise billing terms handled outside Stripe (would go through `enterprise` plan's "custom" pricing manually, not a new billing subsystem).
- Multi-currency support (no current requirement).

**Requires explicit instruction to modify** — see `CLAUDE.md`.
