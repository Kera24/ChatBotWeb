# Widget Pilot Verification Runbook

Status: TASK-066B2 synthetic verification foundation

This runbook verifies a widget release against synthetic real-backend fixtures. It does not deploy production infrastructure and must not use customer data.

## 1. Prepare Isolated Environment

Use a repository checkout at the intended release commit.

The default suite creates an isolated in-memory SQLite database. Do not point the suite at staging, production, or customer databases.

## 2. Build Release Artifact

```bash
npm run widget:release:build
```

This produces provider-neutral release artifacts under `artifacts/widget-release/`.

## 3. Run Pilot Verification

```bash
npm run widget:pilot:verify
```

The command performs release validation/build/inspection/bundle checks and then runs the synthetic real-backend API isolation suite.

## 4. Inspect Report

Open:

```text
artifacts/widget-pilot-verification/report.json
```

Confirm:

- `overall_status` is `passed`
- config smoke passed
- session smoke passed
- message smoke passed
- retrieval smoke passed
- tenant isolation passed
- session isolation passed
- origin isolation passed
- token isolation passed
- cache isolation passed

The report contains safe metadata only and must not include tokens, prompts, message bodies, answers, credentials, or customer data.

## 5. Failure Handling

Use safe diagnostics only:

- failing test name
- HTTP status
- public error category
- synthetic widget label
- release version
- request ID where available

Do not print or request session tokens, database credentials, raw prompts, or customer content.

## 6. Cleanup

The default suite uses an isolated in-memory database and tears it down at test completion. If a future persistent integration database is used, cleanup must remain scoped to `synthetic-widget-b2` fixtures only.

## 7. Pilot Decision

Passing `npm run widget:release:build` is insufficient for controlled pilot deployment. The pilot gate requires:

- release build and production inspection
- real-backend config smoke
- real session smoke
- real message smoke
- positive retrieval
- negative cross-tenant retrieval
- session isolation
- origin isolation
- token/cache isolation

Operational controls, monitoring, rollback, and pilot enablement remain TASK-066B3.

## TASK-066B3 Readiness Follow-Up

After `npm run widget:pilot:verify`, run:

```bash
npm run widget:pilot:readiness
```

The readiness command confirms operational configuration, production inspection, bundle checks, and the B2 report before a pilot release can proceed.

## Azure Deployment Smoke Hook

TASK-068B2 adds a deployed endpoint smoke hook for Azure staging/pilot URLs. It covers HTTPS availability for API health, web, widget iframe, and SDK alias endpoints.

The deeper real-backend browser smoke and synthetic cross-tenant validation remain mandatory before real pilot enablement and are completed by TASK-068B4/B5 deployment gates.
