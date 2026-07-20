# Widget Production Delivery, Security, and Versioning

Status: Implemented foundation for TASK-066B1

## Infrastructure Model

Repository discovery found Dockerfiles for `apps/api` and `apps/web`, local `docker-compose.yml`, GitHub Actions verification, and no committed CDN, reverse-proxy, DNS, Terraform, Kubernetes, Cloudflare, Azure, AWS, Vercel, Netlify, or other production delivery provider configuration. TASK-066B1 therefore implements provider-neutral release artifacts and header/cache policy manifests only.

No production infrastructure is provisioned or mutated by these changes.

## Release Configuration

Release validation uses public, non-secret origins:

- `WIDGET_PUBLIC_ORIGIN` - hosted iframe application origin.
- `WIDGET_PUBLIC_API_ORIGIN` - public widget API origin.
- `WIDGET_SDK_PUBLIC_ORIGIN` - SDK/static CDN origin.
- `WIDGET_RELEASE_ENVIRONMENT` - `development`, `test`, `staging`, `pilot`, or `production`.
- `WIDGET_RELEASE_CHANNEL` - `pilot` or `stable`.

For `staging`, `pilot`, and `production`, origins must be HTTPS, origin-only, credential-free, and non-localhost. Defaults are safe placeholder HTTPS origins so CI can validate the artifact path without secrets.

## Version Model

`packages/widget-sdk/package.json` is the authoritative SDK semantic release version. The current SDK semver is pre-1 foundation release data, while `packages/widget-sdk/src/version.ts` separately records:

- SDK major compatibility: `SDK_MAJOR_VERSION`
- postMessage protocol major: `WIDGET_PROTOCOL_VERSION`
- public API version: `v1` in release metadata

SDK semver, protocol major, and public API version are intentionally separate.

## Release Artifact Layout

`npm run widget:release:build` generates ignored artifacts under:

```text
artifacts/widget-release/
  manifest.json
  sdk/
    v{sdk_version}/loader.js
    v{sdk_major}/loader.js
    v{sdk_major}/alias.json
  widget/
    index.html
    release.json
    assets/
  deployment/
    headers.json
```

The semantic SDK asset is immutable. The major alias is a copy plus alias metadata so object storage/CDNs that do not preserve symlinks can still publish atomically.

## Manifest and Integrity

`manifest.json` contains schema version, release channel/environment, SDK version, SDK major, protocol major, API version, Git commit, UTC timestamp, public origins, artifact paths, cache policies, SHA-256 checksums, SRI for pinned semantic loader use, and gzip byte summaries.

Checksums support release verification and rollback confidence. They are not authentication mechanisms.

## Cache Matrix

| Resource | Cache-Control | ETag | CDN cache | Invalidation |
| --- | --- | --- | --- | --- |
| Immutable SDK semver loader | `public, max-age=31536000, immutable` | Optional | Yes | Never mutate; publish new semver |
| SDK major alias loader | `public, max-age=300, must-revalidate` | Recommended | Yes, short TTL | Replace alias artifact to roll forward/back |
| Iframe HTML | `no-cache` | Recommended | Revalidate only | Replace HTML to move iframe release |
| Iframe hashed JS/CSS/assets | `public, max-age=31536000, immutable` | Optional | Yes | Content-hash change |
| Public config | `public, max-age=60, stale-while-revalidate=30` | Required | Allowed with path/origin isolation | ETag revalidation/publish update |
| Session creation | `no-store` | No | No | Not cached |
| Message | `no-store` | No | No | Not cached |

## Header Policy

`deployment/widget/headers.json` defines provider-neutral policies for SDK semantic paths, SDK major alias paths, iframe HTML, and hashed iframe assets.

Key decisions:

- SDK assets use `Cross-Origin-Resource-Policy: cross-origin` so customer pages can load the loader.
- Iframe HTML is revalidated and gets CSP, `nosniff`, `no-referrer`, restrictive Permissions Policy, and CORP compatible with embedding.
- `COOP` and `COEP` are not set because cross-origin isolation is not required and can break embeddability.
- HSTS is documented as an HTTPS-edge header, not applied by local static artifacts.

## CSP and Frame Ancestors

The provider-neutral iframe CSP is strict for resources but uses broad HTTPS frame-ancestor compatibility because approved customer origins vary per widget and no dynamic edge policy exists yet. Tenant-specific embedding authorization remains enforced by runtime origin validation, public key validation, handshake validation, and session policy.

A future deployment provider can tighten `frame-ancestors` if it supports dynamic tenant-specific headers.

## Public API Headers

Public config retains ETag and `Vary: Origin`. Session and message responses now explicitly return `Cache-Control: no-store`, including successful token/session-state responses. Public API CORS remains explicit, origin-validation-driven, credentialless, and not wildcarded.

CORS is not authentication; origin, public credential, anonymous session, and tenant-scoped RAG checks remain application controls.

## Sandbox and Permissions

The SDK-created iframe currently uses:

```text
sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
referrerpolicy="strict-origin-when-cross-origin"
loading="lazy"
title="Yoranix chat widget"
```

`allow-same-origin` is required by the current iframe-owned `sessionStorage` and same-origin application runtime model. This keeps tokens inside the iframe origin but means sandbox isolation depends on cross-origin hosting, CSP, and strict postMessage validation. This should be revisited if storage architecture changes.

## SRI Policy

Pinned semantic SDK embeds may use the generated `sha384` SRI value. Mutable major aliases should not use fixed SRI unless the embed snippet is updated with every alias move.

## Commands

```bash
npm run widget:config:validate
npm run widget:release:build
npm run widget:inspect:production
npm run widget:bundle:check
npm run widget:e2e:release
```

`npm run verify` now exercises the release artifact build and production inspection path.

## Current Exclusions

TASK-066B1 does not deploy, publish, change DNS, provision CDN/cloud resources, implement monitoring, create synthetic backend tenants, add kill switches, or change widget product behavior.

## TASK-066B3 Operational Controls

TASK-066B3 adds provider-neutral operational controls for controlled pilot readiness: `/health/live`, `/health/ready`, safe request correlation IDs, privacy-preserving redaction helpers, in-memory operational counters for test evidence, server-side pilot allowlist controls, global/widget/message kill switches, provider-neutral alert definitions, a dry-run rollback planner, and `npm run widget:pilot:readiness`. It does not deploy production infrastructure or add a monitoring vendor.

## TASK-067B1 Administration Boundary

Authenticated widget administration APIs create and publish revisioned configuration snapshots. Public-key rotation, embed version selection, and release-channel management are not part of B1 and remain separate from the production delivery/versioning model.

## TASK-067B2 Embed Administration Update

TASK-067B2 adds an admin-facing supported SDK resolver backed by `deployment/widget/sdk-versions.json`. The default embed mode uses the managed major alias `/widget-sdk/v1/loader.js`; pinned mode uses an approved immutable semantic loader path and may include SRI when generated release metadata is available. The admin API does not allow arbitrary SDK URLs or `latest`.

The current snippet generator uses the provider-neutral CDN placeholder from release documentation until approved production domains are wired by deployment configuration. No production deployment or CDN mutation is performed.
