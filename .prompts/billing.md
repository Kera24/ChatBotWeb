# Prompt Template: Billing

Use this when the task touches Stripe subscriptions, plans, invoices, or the billing dashboard. **This area requires explicit instruction to modify pricing/limits/webhook logic — confirm scope before starting if the request is ambiguous.**

## Scope

`apps/api/app/billing/*`, `apps/api/app/api/v1/billing.py`, `apps/api/app/api/v1/billing_webhook.py`, `apps/api/app/db/models/billing.py`, `apps/web/app/billing/*`, `apps/web/components/billing/*`. See `docs/architecture/billing.md`.

## Constraints

- Never change `PLAN_CATALOG` pricing/limits without explicit instruction — this is a business decision.
- Never write `Subscription`/`Invoice` state from anywhere except the webhook handler's verified-event path (`apply_stripe_subscription_event`/`apply_stripe_invoice_event`).
- The webhook handler must always return 200, even on internal failure (Stripe retry semantics) — do not "fix" this into raising an error status.
- All billing route access goes through the `BillingGateway` abstraction, never the raw Stripe SDK directly from a route.
- Mutation endpoints (`checkout-session`, `cancel`, `resume`) are `org_owner`-only.

## Validation

`npm run api:test` (billing test files). If frontend changed, also `npm run web:test && npm run web:lint && npm run web:build`.

## Reporting

Full Report always — billing changes affect revenue and customer-facing financial state; be explicit about exactly what changed and why, even for a small fix.

## Expected output

Changes confined to the billing feature area, with the actual webhook/checkout flow logic traced through in the report (not just "billing updated").

## What NOT to modify

- `PLAN_CATALOG` values (pricing, assistant limits) without explicit instruction.
- The webhook's signature verification or its always-200 response behavior.
- Any other feature's files as a side effect of a billing change.
