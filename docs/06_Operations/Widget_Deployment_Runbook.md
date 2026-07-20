# Widget Deployment Runbook

Status: Foundation runbook updated through TASK-066B2

This runbook describes repository-local release artifact preparation and synthetic real-backend pilot verification. Publishing, CDN configuration, DNS changes, production monitoring, and production rollout remain future tasks.

## 1. Prerequisites

- Node.js 20+
- Widget and SDK dependencies installed
- Git checkout at the intended release commit
- Public, non-secret release origins configured through environment variables or accepted placeholder defaults for CI validation

## 2. Configure Environment

Set production-like values before preparing real pilot artifacts:

```bash
WIDGET_RELEASE_ENVIRONMENT=pilot
WIDGET_RELEASE_CHANNEL=pilot
WIDGET_PUBLIC_ORIGIN=https://widget.example.com
WIDGET_PUBLIC_API_ORIGIN=https://widget-api.example.com
WIDGET_SDK_PUBLIC_ORIGIN=https://cdn.example.com
```

Do not use localhost, mock API origins, credentials, paths, query strings, or fragments for staging/pilot/production.

## 3. Validate Configuration

```bash
npm run widget:config:validate
```

The command validates origins, release channel, release environment, SDK semver, SDK major, protocol major, and public API version metadata.

## 4. Build Release Artifacts

```bash
npm run widget:release:build
```

This validates configuration, builds the SDK, builds the iframe widget, generates versioned SDK artifacts, generates the major alias artifact and manifest, copies iframe hashed assets, copies the provider-neutral header manifest, runs production inspection, and checks bundle budgets.

## 5. Inspect Manifest

Open:

```text
artifacts/widget-release/manifest.json
```

Confirm SDK version, SDK major alias, protocol major, API version, release channel, origins, checksums, and gzip sizes.

## 6. Verify Checksums

Compare the manifest SHA-256 values with the generated loader files before publishing artifacts through a CDN/object store.

## 7. Run Release Verification

```bash
npm run widget:e2e:release
```

This serves generated artifacts locally through the browser test topology and verifies the major alias loader can mount the iframe and call the mock public API from the iframe origin.

## 8. Publish Immutable Artifacts - Future Boundary

A future deployment task will publish `sdk/v{sdk_version}/loader.js` and `widget/assets/*` with immutable cache headers. Do not mutate these paths after publication.

## 9. Update Major Alias - Future Boundary

A future deployment task will publish or replace `sdk/v{sdk_major}/loader.js` and `sdk/v{sdk_major}/alias.json` with short TTL headers. Rollback repoints or replaces this alias with a previous known-good loader copy.

## 10. Verify Headers - Future Boundary

Adapt `deployment/widget/headers.json` to the selected CDN/reverse proxy and verify cache, CSP, referrer, permissions, CORP, and nosniff headers before controlled pilot enablement.

## 11. Pre-Pilot Synthetic Real-Backend Gate

Run:

```bash
npm run widget:pilot:verify
```

This command rebuilds release artifacts, runs production inspection and bundle checks, then verifies synthetic real-backend config/session/message smoke, tenant isolation, session isolation, origin isolation, retrieval isolation, and cache isolation. Passing `npm run widget:release:build` alone is insufficient for controlled pilot deployment. See `docs/06_Operations/Widget_Pilot_Verification_Runbook.md`.

## 12. Rollback Reference

Rollback preparation requires retained previous release manifests and immutable artifacts. SDK alias rollback should not require rebuilding. Iframe rollback should restore a previous iframe HTML/release mapping and then rerun smoke tests.

## TASK-066B3 Operational Readiness Gate

Before any future controlled pilot deployment, run:

```bash
npm run widget:pilot:readiness
```

This gate validates operational configuration, requires the B2 pilot verification report to pass, checks production inspection and bundle budgets, and writes `artifacts/widget-pilot-readiness/report.json`. It covers repository Gates 1-4 only; staging/pilot deployment, post-deploy real smoke, and controlled tenant enablement remain separate operational steps.
