# Skill: Deployment

## Purpose

Work on Docker Compose, Caddy, backup/restore, or Azure infrastructure config. **High blast-radius — confirm explicit instruction before starting.**

## When to use

Any task touching `docker-compose*.yml`, `deployment/**`, the API/web Dockerfiles, or `infrastructure/azure/**`. Full reference: `docs/architecture/deployment.md`.

## Architecture assumptions

Production target is a single VPS via Docker Compose (`docker-compose.prod.yml`), not Azure — Azure infra is kept live for a future migration only. The observability stack is optional and additive (`docker-compose.observability.yml`, combined via `-f`). Caddy is the only service publishing host ports in production.

## Files typically modified

Depends entirely on what was explicitly asked for — this skill has no default "typical" file set beyond: new additive compose profiles/config files, following the existing project-name/network-isolation conventions.

## Files never modified without explicit instruction

- `docker-compose.prod.yml`
- `deployment/caddy/Caddyfile`
- `deployment/backup/backup.sh`, `deployment/backup/restore.sh`
- `infrastructure/azure/**`
- `.github/workflows/*`

## Validation commands

```
docker compose -f <files> config --quiet
```
Create a throwaway `.env.production`-equivalent file only if needed to validate `env_file:` directives resolve, then delete it before finishing — never leave a fabricated secrets file in the repo.

## Expected report format

Full Report always.

## Common pitfalls

- Merging a new optional service into the required production compose file instead of a separate additive one.
- Reusing a Compose project `name:` or container name that could collide with the local-dev compose project.
- Publishing a new service's port to `0.0.0.0` instead of `127.0.0.1` when it shouldn't be internet-reachable (see Grafana in the observability stack for the reference pattern).
- Forgetting `docker compose config` needs a real (even if throwaway/dummy) env file for services using `env_file:` directives, separate from `--env-file` used for `${VAR}` interpolation only.

## Best practices

- Validate syntax with `docker compose config` before ever attempting a real `up`.
- Keep new infrastructure provider-neutral (OpenTelemetry over vendor lock-in) per the deployment philosophy in `CLAUDE.md`.
- Document resource estimates for any new service added to the VPS stack (see `docs/06_Operations/Grafana_Prometheus_Loki_Tempo_VPS_Guide.md` for the reference format).
