# Runbook: Billing Outage

## Symptoms

Stripe webhooks failing to deliver/process, checkout/portal redirects failing, or subscription state visibly stale.

## Diagnosis

1. Check Stripe's own status page for a Stripe-side outage.
2. Check webhook endpoint reachability and processing logs — remember the handler always returns 200, so "failure" here means internal processing failure, not delivery failure.
3. Check for a backlog of unprocessed webhook events.

## Recovery

1. If Stripe-side: no fix available, wait it out, communicate to affected tenants if checkout is blocked.
2. If Conversa-side processing failure: diagnose per `docs/sops/billing-issue.md` — **requires explicit instruction before any billing-logic fix is deployed**.
3. Once fixed, replay/reconcile any backlogged webhook events against current Stripe state (don't assume order-of-arrival is preserved).

## Validation

Webhook processing resumes; subscription states reconciled against Stripe's actual record.

## Escalation

Any billing-logic change requires explicit sign-off per `CLAUDE.md` — escalate rather than deploying a fix unilaterally even during an outage.

## Post-incident review

Was any tenant's subscription state incorrect during the outage window? Confirm full reconciliation, not just that new events are flowing again.
