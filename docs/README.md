# Documentation Index

This folder is the single source of truth for the ChatBotWeb / Yoranix AI Platform.

## Start here (developer operating system + engineering brain)

For anyone (human or Claude Code) doing engineering work in this repository, start at the project root `CLAUDE.md`, then `docs/engineering-index.md` (the master index of current-state engineering docs, ADRs, future specs, roadmap, and principles), then:

- `CONSTITUTION.md` — mission, vision, engineering/product/architecture philosophy, launch/scaling strategy.
- `architecture/` — one current-state doc per subsystem (overall-system, frontend, backend, authentication, billing, retrieval, memory, evaluation, guardrails, observability, knowledge-ingestion, vector-storage, deployment, testing, future-roadmap). **This is the accurate, current-state architecture reference** — supersedes the early draft docs listed below where they overlap.
- `design/design-system.md` — the accurate, current-state UI/design reference — supersedes `05_Design/01_Design_System.md` where they overlap.
- `file-boundaries.md` — which files belong to which feature, and what's off-limits.
- `validation-policy.md` / `reporting-policy.md` / `token-optimisation.md` / `development-playbook.md` — how to validate, report, and work efficiently.
- `../.skills/` and `../.prompts/` (repo root) — reusable skill references and prompt templates per feature domain, meant to make future task prompts short.

## Original foundation documents (early drafts, kept for historical intent)

- `00_Project_Charter/README.md` — project purpose, scope, risks, and success criteria
- `01_Product/01_Product_Vision.md` — product direction, target customers, pillars, and MVP promise
- `02_Architecture/01_System_Architecture.md` — early (v0.1 draft) target architecture sketch; see `architecture/overall-system.md` for current state
- `03_AI/01_RAG_Architecture.md` — ingestion, retrieval, answer generation, evaluation, and safety rules
- `04_Engineering/01_Development_Roadmap.md` — phased development roadmap
- `04_Engineering/02_AI_Assisted_Development_Tasks.md` — Codex/Cursor-friendly task breakdown
- `05_Design/01_Design_System.md` — early (v0.1 draft) design direction; see `design/design-system.md` for current state
- `adr/0001-platform-architecture.md` — first architecture decision record
- `00_Foundation/AI_PLATFORM_MANIFESTO.md` — mission, architectural principles, AI safety principles (canonical, still current)

## Documentation rules

1. Product decisions go under `01_Product`.
2. Architecture decisions go under `02_Architecture` or `adr`.
3. AI, RAG, retrieval, prompts, and evaluation go under `03_AI`.
4. Engineering plans, task breakdowns, and standards go under `04_Engineering`.
5. UI, design system, and interaction patterns go under `05_Design`.
6. Security, compliance, and permissions will go under `06_Security`.
7. Roadmaps and release plans will go under `07_Roadmap`.

## Next documents to create

1. Product Requirements Document
2. Software Requirements Specification
3. Database Design
4. API Specification
5. Security and RBAC Model
6. MVP Implementation Plan
7. Local Development Setup

## Development rule

Do not begin production implementation until each MVP feature has clear requirements, acceptance criteria, and a corresponding engineering task.
