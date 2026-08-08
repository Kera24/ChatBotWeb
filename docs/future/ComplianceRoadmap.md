# Compliance Roadmap

## Purpose

Define the path toward formal compliance certifications/controls (e.g. SOC 2-style controls, data processing agreements, audit logging guarantees) as enterprise tenants require them.

## Current limitation

No formal compliance framework exists today; privacy/security controls exist (redaction, tenant isolation, RBAC — `docs/engineering/security.md`) but aren't organized against a named compliance standard.

## Why postponed

No current tenant requires formal certification; compliance work is expensive and specific (control-by-control), and premature investment without a named target (which standard, which tenant's requirement) risks solving the wrong problem.

## Dependencies

- A concrete enterprise/regulated-industry tenant requirement.
- `docs/future/EnterpriseSSO.md` (SSO is typically a compliance-adjacent requirement for the same tenant profile).
- Mature audit-event coverage (existing `audit_events`-style logging, extended as needed).

## Implementation phases

1. Gap analysis against the specific standard the first requiring tenant needs (e.g. SOC 2 Type I/II) — scope determined by actual demand, not assumption.
2. Close identified control gaps (access review cadence, formal incident response process, data retention policy documentation — much of which already exists informally and needs formalizing, not rebuilding).
3. Engage a third-party auditor once controls are believed complete.
4. Maintain certification (ongoing evidence collection) as a recurring, budgeted process, not a one-time project.

## Technical design

Primarily process/documentation work, not a single technical build — though it may require additional audit-log retention, formal access-review tooling, or MFA (see `docs/engineering/authentication.md`'s out-of-scope note on MFA being bundled here).

## Evaluation plan

Formal third-party audit is the evaluation mechanism itself; internal readiness reviewed against the target standard's control list before engaging an auditor.

## Rollback strategy

Not applicable in the traditional sense — compliance controls, once adopted, generally shouldn't be rolled back; this section exists per the required template but has no meaningful reversal path.

## Success metrics

Successful completion of the targeted compliance certification for the requiring tenant segment.
