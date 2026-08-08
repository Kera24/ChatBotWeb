# Release Type: Internal

For changes deployed only to internal/staging environments, never customer-facing.

## Entry criteria

Passes the narrowest test suite for the touched area (`docs/validation-policy.md`); no requirement for full `npm run verify`.

## Exit criteria

Deployed to staging and confirmed to start/run without error.

## Evaluation requirements

Evaluation gate run required only if the change touches the AI pipeline; advisory grader review optional.

## Rollback

Redeploy the prior staging image — no customer impact, so rollback urgency is low.

## Monitoring

Basic smoke check; no extended monitoring window required.

## Approval requirements

Self-approved by the implementer; no separate reviewer required for purely internal/staging changes.
