# Billing Checklist

## Required validation

- `npm run api:test` covering billing/webhook tests.
- **Requires explicit instruction to modify billing logic, pricing, or webhook handling at all** — see `CLAUDE.md`'s "Things Claude must NEVER do."

## Things to verify

- Webhook handler always returns 200 regardless of internal processing outcome (Stripe retry semantics depend on this).
- `PLAN_CATALOG` (`apps/api/app/billing/plans.py`) changes match the explicit instruction exactly — no incidental plan/pricing drift.
- `BillingGateway` Protocol abstraction is preserved — no Stripe-specific logic leaking into code that should be gateway-agnostic.
- No billing/payment data logged unredacted.

## Common mistakes

- Changing webhook response codes based on internal error handling (breaks Stripe's retry model).
- Modifying pricing/plan data as a side effect of an unrelated task.

## Required documentation

- Update `docs/engineering/billing.md`/`docs/architecture/billing.md` for any billing-flow change, with the explicit instruction that authorized it noted in the report.

## Definition of Done

Explicit instruction obtained and referenced; webhook 200-always behavior preserved; `BillingGateway` abstraction intact; billing tests pass.
