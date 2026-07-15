# TASK-063B2 - Public Message Abuse And Cost Controls

## Objective

Implement the internal abuse-screening and cost-protection foundation for future public widget messages. This task evaluates a `PreparedPublicMessage` before retrieval, RAG, AI Core, or provider execution.

## Scope

- Deterministic rule-based abuse screening.
- Repeated-message fingerprint checks using recent `public_message_requests` state.
- Cost policy, local token estimation, model/pricing resolution, and optional quota checks.
- Combined security preparation service returning `SecuredPublicMessage`.
- Idempotency failure integration for security rejection.
- Optional terminal session blocking only for an explicit block decision.
- Internal-only `message_send` gateway extension after TASK-063B1 preparation.

## Non-Goals

- No public message route.
- No public HTTP message schemas.
- No external moderation provider.
- No embeddings or semantic moderation.
- No retrieval, RAG, AI Core, provider execution, user/assistant message persistence, output sanitisation, streaming, widget SDK/UI, billing, or quota table.

## Acceptance Criteria

- Abuse and cost-control modules exist.
- Rules are deterministic, conservative, individually testable, and return reason codes without raw messages.
- Cost decisions use server-owned ceilings and the AI model registry.
- Optional usage/quota abstraction exists with deterministic in-memory test implementation.
- Security service marks idempotency failed on rejection and leaves the already-consumed slot intact.
- Gateway can call security after preparation only when explicitly injected.
- Existing preparation, session, config, and public access tests remain passing.
