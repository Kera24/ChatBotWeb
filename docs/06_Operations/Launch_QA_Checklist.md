# Launch QA Checklist

Consolidates the customer-journey, security, billing, and performance
findings from the launch-readiness audit into one actionable list. See the
full audit report for detailed evidence/file references behind each line.

## Release gate (run before every production deploy)

```bash
npm run vps:release:gate -- --env-file .env.production
```

Runs, in order: required-env-var check, migration apply, `api:test`,
`web:test`/`web:lint`/`web:build`, `eval:test`, `eval:launch` (launch
threshold gate), and a real-embedding evaluation if Ollama is reachable.
Writes `artifacts/release-gate/report.json`. Non-zero exit = do not deploy.
Add `--smoke-base-url https://<domain>` once something is already deployed,
to also run a live smoke check.

## Customer journey - automated coverage confirmed

All 24 steps in the launch spec have test coverage except the three gaps
below (see the audit's customer-journey table for the full per-step
file mapping):

- [ ] **Gap: landing page** has no automated test. Manual click-through before each launch, or add a smoke test asserting the page loads and key CTAs render.
- [ ] **Gap: no single pipeline test** chains upload -> extract -> chunk -> embed -> index end-to-end (each stage is unit/integration-tested separately). Manually verify this chain once per release by uploading a real document through the UI and confirming it becomes citable, or add an integration test if this becomes a recurring regression source.
- [ ] **Gap: no test proves a widget-sent message becomes visible in the dashboard.** `tests/widget-browser` covers the widget side, `test_conversation_history_api.py`/dashboard component tests cover the dashboard side with mocked data, but nothing connects them. Manually verify once per release: send a message via the public widget, confirm it appears in the Conversations dashboard.

## Security - confirmed present (no action needed)

Tenant isolation, assistant-level RAG isolation, citation-spoofing
protection, prompt-injection/system-prompt-extraction guardrails, upload
validation (type/size/path-traversal), and public-widget origin/rate
limiting are all implemented and test-covered - see the audit's security
section for file references.

## Security - action items before/at launch

- [ ] **Verify `APP_ENV=production` is actually set** in `.env.production` - the session cookie's `Secure` flag and several dev-mode bypasses key off this exact value.
- [ ] **Regenerate every secret** in `.env.production` (`AUTH_SESSION_HASH_SECRET`, `RATE_LIMIT_IDENTITY_SECRET`, `PUBLIC_SESSION_TOKEN_HASH_SECRET`, `PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET`) - each ships an insecure default in code and nothing enforces overriding it.
- [ ] **Confirm Postgres/Redis are not published to the host** - `docker-compose.prod.yml` does not publish them (fixed from the local dev compose file, which does publish both) - verify with `docker compose -f docker-compose.prod.yml --env-file .env.production ps` that only `caddy` has a `PORTS` column entry.
- [ ] Decide whether the current auth-endpoint rate limiting (in-memory, single-process - fine for this single-`uvicorn`-process deployment) is acceptable, or whether to move it to the Redis-backed limiter before launch.
- [ ] No CSRF token mechanism exists (relies on `SameSite=Lax` + single-origin CORS) - accepted risk for launch per this audit; revisit if third-party embedding of the authenticated app (not the public widget) is ever needed.
- [ ] Dependency vulnerability scanning has not been run as part of this audit (no `npm audit`/`pip-audit` report exists) - run one before launch if you haven't recently: `npm audit --omit=dev` per JS package, `pip list --outdated` or a `pip-audit` run against `apps/api/requirements.txt` in a venv.

## Billing - launch without Stripe configured, or complete the checklist first

See [Stripe_Setup_Checklist.md](./Stripe_Setup_Checklist.md) in full. Key
point: leaving Stripe unconfigured is a supported launch state (checkout/
portal return 400, webhook returns 503, trial provisioning still works) -
only complete the Stripe checklist once you intend to actually charge
customers.

## Performance/reliability - verified during this audit

- [x] 50 concurrent requests to `/health/ready` on a freshly built `api` container all returned HTTP 200 (single `uvicorn` process, no `--workers` flag - adequate for early-access concurrency; revisit if this ever becomes a bottleneck).
- [x] API container recovers to `healthy` ~10s after a restart (well inside the healthcheck's 20s `start_period`).
- [x] Redis interruption: core app stays up and `/health/ready` still reports `ready` (redis is now a visible, non-fatal check); rate limiting degrades per its configured `fail_mode`/`RATE_LIMIT_LOCAL_FALLBACK_ENABLED` setting - not a full outage, but be aware rate-limit protection is reduced while Redis is down.
- [x] Migration-from-empty-database and migration-from-current-head (idempotency) both verified during the backup/restore drill (16 revisions applied cleanly to a fresh DB; re-running against an already-migrated DB is a safe no-op).
- [ ] AI-provider/embedding-provider timeout and malformed-response handling is covered by existing unit tests (`test_ai_core.py`, `test_ai_api.py`, `app/ai/executor.py`, `app/ai/errors.py`) but was not separately re-verified live against a real provider in this audit - do so once you configure a real (non-mock) provider.

## Backup/restore - verified during this audit

- [x] Full drill executed: seeded a synthetic organisation row, took a backup (`deployment/backup/backup.sh`), deleted the row, restored (`deployment/backup/restore.sh --db ... --yes`), confirmed the row was back. Fully isolated from the developer's existing dev database (separate Compose project name, separate volumes).

## Before every launch/relaunch

1. `npm run vps:release:gate -- --env-file .env.production`
2. Manually walk the three journey gaps above.
3. `./deployment/backup/backup.sh` (fresh pre-deploy restore point).
4. Deploy (see [VPS_Deployment_Guide.md](./VPS_Deployment_Guide.md) §4).
5. `node scripts/vps-smoke.mjs --base-url ... --api-url ... --widget-url ...`
6. `./deployment/monitoring/check.sh`
