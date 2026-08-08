# Release Type: Alpha

For early functionality exposed to a small, informed internal or design-partner group, with explicit "this may break" expectations set.

## Entry criteria

Full test suite for the touched area passes; feature is functionally complete enough to be usable, not necessarily polished.

## Exit criteria

Deployed and confirmed reachable by the alpha group; known limitations documented and communicated to participants.

## Evaluation requirements

Evaluation gate required for any AI-pipeline-touching change (`docs/checklists/evaluation-checklist.md`) — alpha does not relax the evaluation-first principle, only the polish bar.

## Rollback

`docs/sops/rollback.md`; alpha participants are informed in advance that rollback may happen without notice.

## Monitoring

Active monitoring during the alpha window; feedback actively solicited, not just passively observed.

## Approval requirements

One reviewer sign-off; explicit confirmation that alpha participants have been informed of the feature's experimental status.
