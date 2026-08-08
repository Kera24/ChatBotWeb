# ADR-0028: Engineering Documentation as a First-Class Deliverable

Status: Accepted
Date: 2026-08-07

## Context

As the platform grew (14+ pipeline stages, 5 observability tables, 18+ ADRs, multiple guardrail layers, an evaluation/grading framework), the cost of re-deriving architectural context for every new task — by a human or by Claude Code — grew with it. Two prior efforts addressed this: a "Developer Operating System" (`CLAUDE.md`, `docs/architecture/`, `.skills/`, `.prompts/` — see `docs/adr/0030-developer-operating-system.md`) covering *current-state* conventions, and this "Engineering Brain" effort (`docs/engineering/`, `docs/adr/`, `docs/future/`, `docs/roadmap/`, `docs/principles/`) covering *decision history and forward-looking plans*. The team had to decide whether this kind of documentation work is a one-off cleanup task or an ongoing, budgeted part of engineering.

## Decision

Treat engineering documentation (current-state architecture references, ADRs for every material decision, future-feature specs, roadmap, principles) as a first-class, ongoing deliverable — not a one-time cleanup, and not optional "nice to have" work done only when time permits.

## Alternatives

- **Documentation as an occasional cleanup task** — rejected: this is the state the project was in before this effort, and it produced exactly the problem being solved (repeated architectural reasoning, drift between docs and reality, an ADR 0018/actual-deployment contradiction that had to be discovered and fixed during this very effort — see `docs/adr/0027`).
- **Rely entirely on code comments and git history instead of standalone docs** — rejected: code explains *what*, git history explains *when*, but neither reliably explains *why* a decision was made, what alternatives were considered, or what would justify revisiting it — the exact gap ADRs exist to fill.

## Tradeoffs

- Gains: every future implementation task (human or Claude Code) can start from `docs/engineering-index.md` instead of re-deriving context from scratch; decisions have a durable, citable record; contradictions (like the ADR 0018 case) become findable and fixable instead of silently persisting.
- Costs: real engineering time spent writing and maintaining documentation instead of shipping product features; documentation can itself drift out of date if not treated as seriously as code (mitigated by making cross-referencing and "Current/Future/Out of scope" framing structural, not optional, per this effort's own template).

## Consequences

- New material engineering decisions get an ADR at the time they're made, not retroactively reconstructed later.
- New future-facing feature ideas get a spec under `docs/future/` before implementation starts, per `docs/roadmap/roadmap.md`'s process.
- Documentation review (checking for contradictions, duplication, staleness) is part of finishing a task, not a separate task someone else does later.

## Future reconsideration triggers

None expected as a reversal; this ADR would only be revisited if the documentation structure itself (not the commitment to maintaining it) needed to change shape.
