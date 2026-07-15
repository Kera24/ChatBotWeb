# Current Sprint

Current phase: Sprint 3C - Public Channels
Current task: TASK-063B2 - Public Message Abuse and Cost Controls

## Active Objective

Implement the internal public-message abuse-screening and cost-protection foundation. The security layer evaluates `PreparedPublicMessage` before any retrieval, RAG, AI Core, or provider execution.

## Guardrails

- Do not expose `POST /api/v1/widget/{public_key}/messages`.
- Do not call retrieval, RAG, AI Core, providers, external moderation, abuse providers, or billing systems.
- Do not create public message HTTP schemas, widget SDK/UI, streaming, user/assistant messages, output sanitisation, or migrations.
- Public clients never choose tenant, conversation, model, provider, prompt, retrieval, context, output tokens, timeout, or quota policy.

## Definition Of Done

- Planning task file exists.
- Abuse contracts/rules/service exist.
- Cost-control contracts/policies/service/usage abstraction exist.
- Combined security-preparation service exists.
- Gateway has an injected internal-only security handoff after preparation.
- Focused and adjacent tests pass.
- Docs and `.env.example` are updated.
- `git diff --check` passes.
