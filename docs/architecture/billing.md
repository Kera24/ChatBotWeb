# Billing Architecture

Stripe-backed subscriptions. **Never modify billing logic, pricing, or webhook handling without explicit instruction** — see `CLAUDE.md`.

## Plans

`apps/api/app/billing/plans.py::PLAN_CATALOG`: `starter` ($0, 1 assistant), `professional` ($249/mo, 10 assistants), `enterprise` (custom, unlimited). `LEGACY_PLAN_ALIASES` maps old seeded plan keys (`mvp`→starter, `pilot`→professional) for backward compatibility with existing data.

## Gateway abstraction

`app.billing.gateway.BillingGateway` (Protocol): `ensure_customer`, `create_checkout_session`, `create_portal_session`, `cancel_subscription`, `resume_subscription`, `construct_event`. `LiveBillingGateway` is the Stripe SDK implementation. Constructed once (`create_billing_gateway()` in `app.main.create_app`), retrieved per-request via `get_billing_gateway(request)`. This abstraction exists so billing logic is never called against the raw Stripe SDK directly from a route.

## Data model

- `Subscription` (`app/db/models/billing.py`) — one per organisation (unique constraint), `plan_key`, `status` (default `trialing`), Stripe customer/subscription/price IDs, `trial_ends_at`, `current_period_start/end`, `cancel_at_period_end`.
- `Invoice` — a local read cache of Stripe invoices (amount, status, hosted/PDF URLs, period).

## Service layer (`app/billing/service.py`)

- `ensure_subscription()` — lazily starts a trial for orgs without a subscription row.
- `enforce_assistant_creation_limit()` — raises `PlanLimitExceeded` at the plan's assistant cap.
- `build_subscription_view()` — API response shape including `trial_days_remaining`.
- `apply_stripe_subscription_event()` / `apply_stripe_invoice_event()` — sync local DB state from a verified Stripe webhook event. This is the **only** place subscription/invoice state should be written from an external signal.

## API

`app/api/v1/billing.py` — `GET subscription`, `GET invoices` (owner/admin read), `POST checkout-session`, `POST portal-session`, `POST cancel`, `POST resume` (owner-only mutations).

## Webhook

`app/api/v1/billing_webhook.py` — `POST /billing/webhook`, verifies `Stripe-Signature`, caps body at 512KB, dispatches `checkout.session.completed`, `customer.subscription.*`, `invoice.*`. **Always returns 200 even on internal failure** (logs + rolls back) so Stripe doesn't retry indefinitely — this is intentional, not a bug to "fix."

## Frontend

`apps/web/app/billing/page.tsx` → `components/billing/billing-dashboard-client.tsx` (Header, Metrics, PlanPicker, InvoiceHistory), checkout/portal redirect handling, cancel/resume gated on `session.role === "org_owner"`.

## Rules

- Never change `PLAN_CATALOG` pricing/limits without explicit instruction — this is a business decision, not an engineering one.
- Never write subscription/invoice state from anywhere except the webhook handler's verified event path.
- Never remove the "always 200" behavior from the webhook handler.
- See `docs/file-boundaries.md` for the exact file list this feature owns.
