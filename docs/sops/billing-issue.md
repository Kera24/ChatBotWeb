# SOP: Billing Issue

## Purpose

Respond to a billing/subscription/webhook problem without introducing further billing-state inconsistency.

## When to use

A Stripe webhook failure, plan/subscription state mismatch, or customer-reported billing discrepancy.

## Step-by-step process

1. **Requires explicit instruction before modifying any billing logic** (`CLAUDE.md`) — diagnosis can proceed immediately, but a code fix needs sign-off.
2. Check webhook delivery/processing logs — the handler always returns 200 regardless of internal outcome, so a missed state update is a processing bug, not a delivery failure, and must be diagnosed as such.
3. Reconcile the tenant's actual Stripe subscription state against Conversa's local record — identify exactly where they diverged.
4. Fix data inconsistency via the `BillingGateway` abstraction, never a direct database patch that bypasses it (would drift from Stripe's own state model again).
5. Get explicit instruction/sign-off before deploying any billing-logic change, per `docs/checklists/billing-checklist.md`.

## Validation

`docs/checklists/billing-checklist.md`; reconciled state matches Stripe's actual subscription record.

## Rollback

Billing state fixes should be additive/corrective, not destructive — if a fix is wrong, correct it forward with another explicit-instruction-gated change, not a raw rollback that could re-diverge from Stripe.

## Success criteria

Tenant's billing state matches Stripe's source of truth; root cause (webhook processing bug vs. data entry error) identified; explicit instruction obtained for any logic change.
