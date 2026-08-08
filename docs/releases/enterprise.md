# Release Type: Enterprise

For features/changes specifically gating enterprise-tenant requirements (SSO, compliance controls, dedicated SLAs — `docs/future/EnterpriseRoadmap.md`).

## Entry criteria

Everything `docs/releases/production.md` requires, plus: security review specific to the enterprise feature (e.g. SSO/SAML integration review, `docs/future/EnterpriseSSO.md`), and confirmation the change doesn't affect non-enterprise tenants' existing behavior.

## Exit criteria

Deployed, validated against the specific requiring enterprise tenant's actual use case, with confirmation their requirement is genuinely met (not just technically shipped).

## Evaluation requirements

Full evaluation gate, plus any enterprise-specific validation (e.g. RBAC-mapping-from-IdP-claims correctness for SSO).

## Rollback

`docs/sops/rollback.md`; enterprise tenants typically have stricter change-notification expectations — confirm their support/success contact is informed of the rollback.

## Monitoring

Extended monitoring window given the higher stakes of enterprise-tenant trust; dedicated attention to the specific enterprise tenant's traffic/behavior if the feature is tenant-specific.

## Approval requirements

Reviewer sign-off plus explicit confirmation this was built in response to a real enterprise requirement (`docs/adr/0026`-style demand-evidence discipline), not spec-ahead-of-demand.
