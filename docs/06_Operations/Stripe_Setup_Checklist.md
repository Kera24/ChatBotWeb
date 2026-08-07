# Stripe Setup Checklist

This is a checklist of **user-supplied tasks in the Stripe Dashboard** -
nothing here is a code change. It does not choose or recommend live pricing;
that is a business decision for you to make. See the billing readiness audit
in the launch report for what the code already does/doesn't do.

You can launch without completing any of this: with `STRIPE_SECRET_KEY`/
`STRIPE_WEBHOOK_SECRET` unset, checkout/portal return HTTP 400 and the
webhook endpoint returns 503, but the rest of the product (including trial
provisioning) works normally.

## One-time setup

- [ ] Create a Stripe account (or use an existing one) and decide test vs. live mode for this launch.
- [ ] Create one Stripe **Product** per plan (Starter, Professional, Enterprise - matching `app/billing/plans.py`'s plan keys).
- [ ] Create one **Price** per product (decide currency and billing interval - a business decision, not made here).
- [ ] Copy each **Price ID** into the corresponding env var: `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PROFESSIONAL`, `STRIPE_PRICE_ENTERPRISE`.
- [ ] Copy the **Secret key** into `STRIPE_SECRET_KEY` (test key `sk_test_...` for a dry run first, live key `sk_live_...` only once you're ready to charge real cards).
- [ ] Copy the **Publishable key** into `STRIPE_PUBLISHABLE_KEY` (present in config for completeness; not currently referenced by any code path - the app does Checkout/Portal server-side via redirect, not Stripe.js client-side).
- [ ] In the Stripe Dashboard, add a **webhook endpoint** pointed at `https://<API_DOMAIN>/api/v1/billing/webhook` (confirm the exact route in `apps/api/app/api/v1/billing_webhook.py`).
- [ ] Subscribe that webhook to at least: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`, `invoice.finalized`.
- [ ] Copy the webhook's **signing secret** into `STRIPE_WEBHOOK_SECRET`.
- [ ] Decide `BILLING_TRIAL_PERIOD_DAYS` (default 14).

## Before opening billing to real customers

- [ ] **Test checkout** end-to-end in Stripe test mode: create an org, start checkout, complete with a [Stripe test card](https://stripe.com/docs/testing), confirm the subscription appears active in the app.
- [ ] **Test the billing portal**: open a portal session for a test org, confirm plan/payment-method management works.
- [ ] **Test cancellation**: cancel a subscription via the app's cancel endpoint, confirm `cancel_at_period_end` is reflected; separately cancel directly in Stripe Dashboard and confirm the `customer.subscription.deleted` webhook updates the app's record.
- [ ] **Test webhook retries**: use the Stripe CLI (`stripe trigger <event>` / `stripe listen --forward-to`) or the Dashboard's "resend" feature to confirm duplicate webhook deliveries don't double-apply state (the app's webhook idempotency is exercised by `apps/api/tests/test_billing_api.py`, but a live retry test against your real endpoint is still worth doing once before launch).
- [ ] Switch `STRIPE_SECRET_KEY`/publishable key/webhook secret from test to live values, and re-point the live webhook endpoint URL.

## Known gaps to be aware of (from the billing readiness audit - not blocking, but plan around them)

- **No plan downgrade/access restriction on cancelled or expired subscriptions.** `subscription.status` is stored but never checked by `enforce_assistant_creation_limit`; a cancelled org keeps its prior plan's assistant limit indefinitely, and `plan_key` is not reset to `starter` on `customer.subscription.deleted`. If you need hard enforcement on cancellation before launch, this needs a code change - not just configuration.
- **No message-quota plan limit.** The only enforced Stripe-plan limit today is assistant count (`enforce_assistant_creation_limit`); the separate `PUBLIC_MESSAGE_DAILY_*_QUOTA` settings are a flat, non-plan-aware cost-control knob, not a billing feature.
- **`invoice.payment_failed` has no distinct handling** - it's stored as an `Invoice` row via the same generic path as `invoice.paid`, with no subscription-status flip or customer notification. If dunning matters for launch, this is a gap to close.
