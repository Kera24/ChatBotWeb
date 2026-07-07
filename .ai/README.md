# .ai Operating System

This folder is the operating system for Codex and future AI coding agents working on ChatBotWeb / Yoranix AI Platform.

It does not replace `docs/`, `planning/`, or `implementation-pack/`. It gives agents a fast, practical entrypoint into those sources and records the rules that must be followed during implementation.

## First file to read

Every Codex session must start with:

1. `.ai/PROJECT_CONTEXT.md`
2. `.ai/CURRENT_SPRINT.md`
3. The relevant agent brief in `.ai/agents/`
4. The relevant context file in `.ai/context/`
5. The task, epic, or implementation-pack file linked from the work item

## Folder map

- `PROJECT_CONTEXT.md` - canonical agent entrypoint and non-negotiable rules
- `CURRENT_SPRINT.md` - current implementation focus and task boundaries
- `AGENTS.md` - how specialist agents should coordinate
- `context/` - durable product, architecture, design, coding, and security context
- `agents/` - role-specific operating briefs
- `prompts/` - reusable implementation and review prompts
- `sprints/` - sprint objectives, scope, guardrails, and exit criteria

## Non-negotiables

- Keep MVP scope strict.
- Preserve tenant isolation in API, database, analytics, widget, and RAG paths.
- Make RAG answers source-grounded and citation-aware.
- Do not commit secrets.
- Do not add dependencies without a clear need and an ADR when the dependency is major.
- Do not implement product features from this folder alone; link work to existing docs, planning items, or a new approved task.

## Related source material

- `README.md`
- `docs/README.md`
- `planning/README.md`
- `implementation-pack/README.md`
- `implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md`
- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
