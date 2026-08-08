# Validation Policy

The goal is to run the narrowest set of commands that actually proves the change is correct — not to run everything, every time. `npm run verify` is comprehensive but slow (several minutes, includes widget Playwright e2e); reserve it for the situations listed below.

## Decision table

| What changed | Run |
|---|---|
| `apps/api/app/**` (routes, services, repositories, models — no migration) | `npm run api:test` |
| `apps/api/alembic/versions/**` (new migration) | `npm run api:test` (schema for tests comes from `Base.metadata`, not the migration itself) **plus** manually validate the migration: `cd apps/api && python -m alembic upgrade head` then `downgrade -1` then `upgrade head` again against a throwaway DB URL, and update `apps/api/tests/test_alembic_compat.py`'s hardcoded head-revision string |
| `apps/api/app/ai/**` or `apps/api/app/evaluation/**` (including `apps/api/app/evaluation/feedback/**`, `production_gate.py`, `feedback_metrics.py`) | `npm run api:test` **and** `npm run eval:test` |
| `apps/api/app/observability/**` | `npm run api:test` (covers `test_ai_trace_*`, `test_observability_api.py`, `test_otel_generic_export.py`) |
| `apps/api/app/repositories/evaluation_candidate_repository.py`, `apps/api/app/api/v1/evaluation_candidates.py`, `apps/api/app/operations/{production_signal_scan,eval_focused_run,eval_regression_report,eval_release_gate_check}.py` | `npm run eval:test` (covers `test_evaluation_candidate_*.py`, `test_production_signal_scan_cli.py`, `test_eval_focused_run_cli.py`, `test_eval_regression_report.py`, `test_eval_release_gate_check.py`) |
| `apps/web/**` | `npm run web:lint && npm run web:build && npm run web:test` |
| `apps/widget/**` | `npm run widget:test && npm run widget:lint && npm run widget:build`; add `npm run widget:e2e:chromium` only if embed-visible behavior changed |
| `packages/widget-sdk/**` | `npm run widget-sdk:test && npm run widget-sdk:lint && npm run widget-sdk:build` |
| `docker-compose*.yml` or `deployment/**` | `docker compose -f <files> config --quiet` (see `.skills/deployment/SKILL.md` for env-file caveats) |
| `.github/workflows/**`, `infrastructure/azure/**` | Do not modify without explicit instruction (see `docs/architecture/deployment.md`); if explicitly asked, there is no local equivalent to CI — describe what you changed precisely and flag that it can only be fully validated by CI/a real Azure environment |
| Any change, before reporting a large/cross-cutting task complete | `npm run verify` |
| Always, whenever any file was touched | `git diff --check` |

## Why `npm run verify` is not the default

It chains `docker compose config`, `api:test`, `eval:test`, `web:test`, `web:lint`, `web:build`, `widget-sdk:test/lint/build`, `widget:test/lint/build`, `widget:release:build`, and `widget:e2e:chromium` (Playwright, ~30s+ alone). Running this for a one-line frontend copy change wastes several minutes proving things that couldn't possibly have broken. Use the decision table above instead, and only reach for `verify` when the change is genuinely cross-cutting (touches shared config used by multiple apps, or you're about to report a large multi-area task as fully complete).

## Full command reference (as of this writing — confirm against `package.json` if it's been a while)

```
api:test            cd apps/api && python -m pytest
eval:test            cd apps/api && python -m pytest tests/test_evaluation_*.py tests/test_golden_dataset_fixture.py tests/test_vector_search_similarity_threshold.py tests/test_ollama_embedding_provider.py tests/test_eval_run_real_cli.py tests/test_production_signal_scan_cli.py tests/test_eval_focused_run_cli.py tests/test_eval_regression_report.py tests/test_eval_release_gate_check.py
web:test              npm --prefix apps/web run test:run   (Vitest)
web:lint               npm --prefix apps/web run lint
web:build              npm --prefix apps/web run build
widget:test            npm --prefix apps/widget run test
widget:lint             npm --prefix apps/widget run lint
widget:build            npm --prefix apps/widget run build
widget-sdk:test        npm --prefix packages/widget-sdk run test  (builds the package first, then runs Vitest against the build)
widget:e2e:chromium    builds widget-sdk + widget test bundle, then Playwright chromium project in tests/widget-browser
verify                  the full chain - see package.json for the exact current command
```

Azure/VPS-release-specific scripts (`azure:*`, `vps:*`, `widget:pilot:*`, `widget:admin:release:verify`) exist for deployment/release verification and are out of scope for routine feature-task validation — only run them if the task is explicitly about a release/deployment gate (see `.skills/deployment/SKILL.md`).

## `git diff --check`

Run this before finishing any task that touched files — it catches trailing whitespace and other diff-hygiene issues cheaply. A clean exit code (0) with only line-ending (`LF will be replaced by CRLF`) warnings is fine; those are informational, not errors.

## What "passes" means

Never report a command as passing without having actually run it in the current session and read its output. A prior session's result, or an assumption based on the code "looking right," does not count.
