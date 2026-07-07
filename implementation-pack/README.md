# Master Implementation Pack v1.0

This folder is the implementation operating system for ChatBotWeb / Yoranix AI Platform.

It translates the product vision, architecture, requirements, and planning documents into practical engineering instructions for humans and AI coding agents.

## Purpose

The pack exists so that Codex, Cursor, Claude Code, or a human engineer can implement the platform consistently without needing repeated verbal context.

## How to use this pack

1. Read the relevant volume.
2. Select the sprint or task.
3. Use the matching prompt from the AI factory volume.
4. Implement in a branch.
5. Review against the quality gates.
6. Update docs if behaviour changes.

## Volumes

- `00_Operating_Model` - how the project is built and governed
- `01_Product` - product rules and MVP boundaries
- `02_Architecture` - system architecture rules
- `03_AI` - RAG and AI implementation rules
- `04_Backend` - backend engineering standards
- `05_Frontend` - frontend engineering standards
- `06_Database` - database and migration standards
- `07_Security` - security and tenant isolation standards
- `08_DevOps` - local development, CI, and deployment standards
- `09_QA` - testing and evaluation standards
- `10_AI_Factory` - prompts, agent workflow, and implementation process

## Non-negotiable rules

1. Do not build features outside MVP scope without an approved task.
2. Do not implement tenant-scoped data access without tenant filtering.
3. Do not expose public widget endpoints without rate-limit planning.
4. Do not add AI calls without usage and cost logging plans.
5. Do not introduce major dependencies without an ADR.
6. Do not ship RAG answers that ignore source grounding.

## Current implementation focus

The immediate focus is the MVP foundation:

1. Backend foundation
2. Frontend foundation
3. Database foundation
4. Tenant management
5. Knowledge upload
6. RAG MVP
7. Website widget
8. Analytics MVP
