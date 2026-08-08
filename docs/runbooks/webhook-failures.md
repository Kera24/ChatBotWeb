# Runbook: Webhook Failures

## Symptoms

Stripe (or future connector-source) webhooks failing to process correctly, detected via processing logs or state-mismatch reports.

## Diagnosis

1. Confirm the webhook endpoint returns 200 (it always should, by design) — a non-200 indicates a bug in the handler itself, not just "processing failed."
2. Check processing logs for the specific exception/failure inside the handler.
3. Determine if this is a signature-validation failure (security-relevant, check for tampering) or a genuine processing bug.

## Recovery

1. Signature-validation failures: verify webhook secret configuration hasn't drifted; if legitimate requests are failing validation, this is urgent (blocks all billing state sync).
2. Processing bugs: fix per `docs/sops/billing-issue.md` (explicit instruction required for billing-logic changes).
3. Replay backlogged events once fixed, reconciling against current source-of-truth state (Stripe, or future connector source systems).

## Validation

New webhook events process correctly; backlog reconciled.

## Escalation

Persistent signature-validation failures may indicate a configuration drift or an actual security concern — escalate per `docs/sops/security-incident.md` if tampering is suspected.

## Post-incident review

Was the always-200 design actually preventing Stripe retries from compounding the problem, or did it mask a longer-than-necessary detection window? Consider whether processing-failure alerting needs strengthening.
