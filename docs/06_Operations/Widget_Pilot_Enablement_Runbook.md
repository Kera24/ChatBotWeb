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
