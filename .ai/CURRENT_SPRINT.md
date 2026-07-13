# Current Sprint

Current phase: Sprint 2C ? Dashboard Integration
Current task: TASK-054

Source sprint plan:

- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `docs/07_Roadmap/01_MVP_Implementation_Plan.md`
- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `docs/04_Engineering/Dashboard_Conversation_History.md`
- `docs/04_Engineering/Frontend_Testing.md`
- `docs/04_Engineering/Unanswered_Review_Workflow.md`
- `planning/tasks/TASK-050-rag-orchestrator-implementation.md`
- `planning/tasks/TASK-051-conversation-history-read-api.md`
- `planning/tasks/TASK-052-dashboard-conversation-history-integration.md`
- `planning/tasks/TASK-053-frontend-testing-foundation.md`
- `planning/tasks/TASK-054-unanswered-fallback-review-workflow.md`

## Sprint goal

Connect dashboard conversation history and knowledge-gap review workflows to tenant-safe APIs while preserving controlled Expressionism, accessibility, privacy exclusions, tenant context, and current temporary-auth boundaries.

## Active priorities

1. Keep dashboard API calls and development auth headers centralised.
2. Review fallback, failed, and low-confidence assistant answers without mutating original message content.
3. Store reviewer decisions in annotation records and audit every review status change.
4. Preserve viewer read access and restrict updates to org owners and client admins.
5. Keep public widget, automated remediation, analytics aggregation, and production auth out of scope.

## Guardrails

- Do not implement production auth, public widget, live public chat, deletion, export, feedback capture from public users, analytics aggregation, search, streaming, real external LLM providers, prompt editing UI, or model configuration UI.
- Do not scatter development headers across components.
- Do not attach dashboard auth headers to any public-widget client.
- Do not expose raw prompts, secrets, provider internals, stack traces, or hidden metadata.
- Do not implement AI-generated knowledge remediation in TASK-054.

## Definition of done for TASK-054

- Review candidates are derived from assistant messages with fallback, failed, or low-confidence answer states.
- Review annotations persist review status, reviewer note, reviewer identity, and review timestamp.
- Backend list/detail/update endpoints are tenant-safe and RBAC-protected.
- Review status updates create audit events.
- Dashboard review list/detail routes exist with filters, pagination, citations, context, and update controls.
- Backend and frontend tests cover review workflow behaviour.
- Documentation and API specification are updated.
- `npm run web:test`, `npm run web:lint`, `npm run web:build`, `npm run api:test`, and `npm run verify` have been run or reported with blockers.

## Next recommended task

Add lightweight knowledge-gap reporting summaries or begin document-update planning without automating remediation.

## Current/Next Planning Task

- `planning/tasks/TASK-054-unanswered-fallback-review-workflow.md`
