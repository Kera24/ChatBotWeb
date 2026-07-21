# Widget Pilot Enablement Runbook

Status: TASK-066B3 pre-deployment enablement model

## Steps

1. Verify release build:

```bash
npm run widget:release:build
```

2. Run synthetic real-backend verification:

```bash
npm run widget:pilot:verify
```

3. Run operational readiness:

```bash
npm run widget:pilot:readiness
```

4. Confirm the widget is otherwise publishable:

- active tenant
- active workspace
- active public widget credential
- published widget configuration
- allowed origins configured
- knowledge corpus ready

5. Enable pilot access through server-side allowlist:

```text
PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED=true
PUBLIC_WIDGET_PILOT_ALLOWLIST=wpk_...
```

6. Restart or reload the API process if environment-based configuration is used.

7. Run real environment smoke:

- config
- session
- message
- token isolation
- origin denial

8. Observe initial traffic through request IDs, safe operational events, and provider-neutral alert signals.

9. Disable or roll back if verification fails.

## Do Not Use

- customer secrets
- session tokens
- browser storage dumps
- production data in synthetic tests

## Pilot State

TASK-066B3 defines the controlled pilot gate. It does not perform production deployment or customer enablement by itself.

## TASK-067B2 Pilot Enablement Dependency

Pilot enablement assumes the widget has at least one active allowed origin and an active current public key. Public key rotation does not grant pilot access and does not publish configuration. After a rotation, rerun config smoke with the new key and expected customer origin before enabling or continuing pilot traffic.

## TASK-067B4 Gate Addition

Before pilot enablement, administrators must verify that the widget has a published revision, at least one valid allowed origin, selected knowledge resources are ready where used, and installation evidence is observed from the intended allowed origin after the embed snippet is installed.

## TASK-067B5 Admin Pre-Pilot Gate

Before using the widget administration workflow for controlled pilot setup, run:

```bash
npm run widget:admin:release:verify
```

Passing B1 release build and B2/B3 pilot gates is insufficient on its own once tenant administrators will create, configure, publish, rotate keys, or roll back widgets through the dashboard.
