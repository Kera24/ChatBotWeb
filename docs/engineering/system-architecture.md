# System Architecture — Current / Future / Out of Scope

## Current

Multi-tenant SaaS: Organisation → Workspace → Assistant (Widget). FastAPI backend (`apps/api`), Next.js dashboard (`apps/web`), embeddable widget iframe + loader SDK (`apps/widget`, `packages/widget-sdk`). Full detail: `docs/architecture/overall-system.md`. Decision record: ADR 0001 (multi-tenant platform, not per-client builds).

## Future

- Second channel beyond the website widget (Slack/Teams/voice), via a new `app.access.channels.*` adapter reusing the same core (see `docs/CONSTITUTION.md`'s "Long-term platform vision").
- Azure as an optional deployment target alongside the VPS (infrastructure kept live, not active — ADR 0029; the VPS-first pivot itself is ADR 0027, superseding ADR 0018's original Azure-first pilot choice).
- See `docs/roadmap/roadmap.md` for sequencing.

## Out of scope (not planned)

- Rewriting the monorepo into separate repositories/services before there is operational evidence scale requires it (see `docs/principles/engineering-principles.md`'s "progressive enhancement").
- A general-purpose plugin/extension marketplace.
