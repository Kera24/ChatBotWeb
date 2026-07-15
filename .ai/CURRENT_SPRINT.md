# Current Sprint

Current phase: Sprint 3C - Public Channels
Current task: TASK-063B4 - Public Output Sanitisation and Security Hardening

## Active Objective

Replace the provisional public widget message projection with a dedicated output-sanitisation and citation-validation boundary.

## Guardrails

- Preserve existing public config/session/message endpoints and security stages.
- Public answers must pass through the output sanitiser before response snapshots are stored.
- Public output must not expose unsafe HTML, executable links, internal IDs, storage paths, prompt/provider metadata, token/cost metadata, stack traces, or system/developer instructions.
- Full widget UI, streaming, file uploads, tools, new providers, public history, and analytics remain out of scope.

## Definition Of Done

- Output sanitisation package exists.
- Public RAG adapter stores only sanitised snapshots.
- XSS/link/leakage/citation tests pass.
- Endpoint integration test proves unsafe output is replaced before snapshot storage.
- Documentation is updated.
- Verification commands pass or failures are reported.