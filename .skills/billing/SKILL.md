# Skill: Billing

## Purpose

Work on Stripe subscriptions, plans, invoices, or the billing dashboard.

## When to use

Any task touching `apps/api/app/billing/*`, `apps/api/app/api/v1/billing*.py`, or `apps/web/app/billing/*`. Full reference: `docs/architecture/billing.md`.

## Architecture assumptions

Billing always goes through the `BillingGateway` abstraction (`Protocol` + `LiveBillingGateway` Stripe implementation), never the raw Stripe SDK from a route. `PLAN_CATALOG` is the single source of pricing/limits. The webhook handler is the *only* place subscription/invoice state is written from an external signal, and always returns 200 regardless of internal outcome.

## Files typically modified

- `apps/api/app/billing/*.py`
- `apps/api/app/api/v1/billing.py`, `apps/api/app/api/v1/billing_webhook.py`
- `apps/api/app/db/models/billing.py` (only if schema change is explicitly requested)
- `apps/web/app/billing/*`, `apps/web/components/billing/*`

## Files never modified

- `PLAN_CATALOG` pricing/limits without explicit instruction.
- The webhook's always-200 response behavior or signature verification.
- Anything unrelated to billing as a side effect.

## Validation commands

```
npm run api:test
npm run web:test
npm run web:lint
npm run web:build
```

## Expected report format

Full Report always — billing affects revenue and customer financial state.

## Common pitfalls

- Writing subscription/invoice state outside the webhook's verified-event path.
- Making the webhook return a non-200 on internal failure (breaks Stripe's retry semantics intentionally relied upon here).
- Changing plan pricing/limits as a "helpful" side effect of an unrelated fix.
- Calling the Stripe SDK directly from a route instead of through `BillingGateway`.

## Best practices

- Trace through `apply_stripe_subscription_event()`/`apply_stripe_invoice_event()` explicitly in your report when touching webhook logic — state exactly which Stripe event types are affected.
- Test webhook changes against realistic Stripe event payload shapes, not simplified ones.
- Confirm `org_owner`-only gating is preserved on any new mutation endpoint.
