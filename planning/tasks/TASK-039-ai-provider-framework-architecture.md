# Task: AI Provider Framework Architecture

## Task ID

TASK-039

## Linked epic/story

- EPIC-003

## Objective

Define the architecture for a future AI Provider Framework that can safely run source-grounded answer generation across multiple model providers while preserving tenant isolation, observability, cost controls, and prompt/version traceability.

This is architecture and planning only. It does not implement code, SDK integrations, LLM calls, final answer generation, chat sessions, widget behaviour, analytics, or background queues.

## 1. Purpose

The AI Provider Framework will provide a provider-agnostic layer between ChatBotWeb's RAG pipeline and external or local LLM providers.

It must support:

- Source-grounded answer generation from TASK-038 prompt assembly outputs.
- Provider substitution without changing retrieval, prompt, citation, or chat orchestration code.
- Deterministic local/mock behaviour for tests and development.
- Future tenant-level model configuration and routing.
- Token, latency, quality, error, and cost tracking.
- Secure handling of provider secrets and prompt metadata.

The framework must not weaken existing RAG rules:

- Never answer from another tenant's data.
- Never guess when retrieved evidence is weak or missing.
- Preserve citations and source traceability.
- Log usage and operational signals when AI calls are implemented.

## 2. Provider Interface

The provider interface should be defined around a small set of stable request and response objects.

### Core request

`AICompletionRequest` should include:

- `organisation_id`
- `workspace_id`
- `prompt_version`
- `system_prompt`
- `user_prompt`
- `context_block_count`
- `citation_count`
- `model_key`
- `temperature`
- `max_output_tokens`
- `response_format`
- `stream`
- `metadata`

### Core response

`AICompletionResponse` should include:

- `provider_key`
- `model_key`
- `model_name`
- `answer_text`
- `finish_reason`
- `raw_response_id`
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `estimated_cost_minor_units`
- `latency_ms`
- `created_at`
- `metadata`

### Core interface

Providers should implement:

```text
complete(request) -> AICompletionResponse
stream(request) -> iterator[AIStreamEvent]
health_check() -> AIProviderHealth
count_tokens(request) -> TokenEstimate
```

The initial implementation should make `stream` optional and return a clear unsupported error until streaming is implemented.

## 3. OpenAI-Compatible Design

The first production provider should follow an OpenAI-compatible chat/completions design because it maps cleanly to the existing prompt assembly output.

The OpenAI-compatible adapter should:

- Convert `system_prompt` into a system/developer message as supported by the target model API.
- Convert `user_prompt` into the user message.
- Use `model_key` to resolve the exact provider model name from the model registry.
- Support non-streaming completion first.
- Support structured response options later.
- Capture provider response ID and finish reason.
- Normalize provider errors into framework error types.
- Report token usage from provider usage fields when available.
- Estimate usage when provider usage fields are missing.

The adapter must not send tenant IDs, secrets, or internal database identifiers unless explicitly needed for observability metadata and approved for that provider.

## 4. Mock Provider Design

A deterministic mock provider is required for tests, local development, and CI.

The mock provider should:

- Accept the same `AICompletionRequest` as production providers.
- Return deterministic answer text from the supplied prompt.
- Respect safe fallback behaviour when context is empty or marked insufficient.
- Include predictable token estimates.
- Include predictable latency metadata.
- Support configurable failure modes for tests.
- Never call external services.
- Never require secrets.

Example mock behaviours:

- If `user_prompt` contains context blocks, return a short answer citing `[1]`.
- If `user_prompt` contains the empty-context fallback line, return a safe fallback answer.
- If configured with `MOCK_AI_FAILURE=true`, raise a normalized provider failure.

## 5. Future Providers

### Azure OpenAI

Azure OpenAI should be implemented as an OpenAI-compatible adapter variant with Azure-specific configuration:

- endpoint URL
- deployment name
- API version
- Azure identity or API key support
- per-tenant deployment routing in the future

### Anthropic

Anthropic support should map framework requests into Anthropic's messages API:

- system prompt goes into Anthropic system field.
- user prompt goes into messages.
- token and stop reason fields are normalized.
- provider-specific safety responses are mapped to framework finish/error reasons.

### Gemini

Gemini support should map prompts into Gemini content structures:

- system instructions where supported.
- user prompt as content parts.
- safety blocks and finish reasons normalized.
- usage metadata mapped into token accounting.

### Ollama/local

Ollama or local model support should be treated as a development/self-hosted provider:

- no external secrets required by default.
- local endpoint URL configured per environment.
- lower trust in token accounting unless model-specific tokenizer is configured.
- explicit warnings that local models may not match production answer quality.

## 6. Model Registry Concept

The model registry should separate platform model keys from provider-specific model names.

A registry entry should include:

- `model_key`
- `provider_key`
- provider model/deployment name
- display name
- context window
- max output tokens
- supports streaming
- supports JSON mode
- supports tools
- input token price
- output token price
- currency
- status: `active`, `deprecated`, `disabled`
- default temperature
- allowed tenant tiers or feature flags

The registry should start as code/config and later move to database-backed admin configuration when tenant-level controls are introduced.

## 7. Prompt Registry Concept

Prompt assembly must remain versioned and auditable.

A prompt registry should track:

- `prompt_key`
- `prompt_version`
- prompt purpose
- system prompt template hash
- user prompt template hash
- compatible model families
- citation policy
- fallback policy
- release status
- created/approved metadata

TASK-038 currently exposes `PROMPT_VERSION`; future AI calls should persist the prompt version and prompt hash on answer records.

## 8. Provider Routing Rules

Routing should resolve in this order:

1. Explicit request override, if allowed for the caller and tenant.
2. Workspace-level model configuration, when implemented.
3. Organisation-level model configuration, when implemented.
4. Platform default model key.
5. Mock provider in test/local environments only when explicitly configured.

Routing must validate:

- provider is enabled.
- model is active.
- tenant is allowed to use the model.
- requested response features are supported by the model.
- budget and rate limit policies permit the call.

## 9. Timeout and Retry Policy

The provider framework should enforce timeouts and retries centrally.

Recommended defaults:

- connect timeout: 5 seconds
- read timeout: 60 seconds for non-streaming calls
- total request timeout: 90 seconds
- retries: up to 2 for transient failures
- retry backoff: exponential with jitter
- no retry for validation, authentication, tenant, content policy, or quota errors unless explicitly safe

Retry attempts must be logged with provider, model, error class, and attempt count.

## 10. Streaming Future Design

Streaming should be added after non-streaming answer generation is stable.

Future streaming events should include:

- `message_start`
- `content_delta`
- `citation_delta` if citations are emitted progressively
- `usage_delta` where supported
- `message_end`
- `error`

The API should abstract provider streaming differences behind `AIStreamEvent` so chat endpoints do not depend on provider SDK event formats.

Streaming must preserve tenant and conversation boundaries and should stop cleanly on client disconnect.

## 11. JSON Mode and Tool-Calling Future Compatibility

The framework should reserve request fields for:

- `response_format`
- JSON schema name/version
- tool definitions
- tool choice
- tool execution policy
- tool call correlation IDs

Initial answer generation should not enable tools. Future tool calling must require explicit allowlists and tenant-safe execution boundaries.

JSON mode should be used only for tasks that require structured output, such as extraction validation, classification, or evaluation metadata.

## 12. Token Accounting Hooks

Token accounting should happen at these points:

- pre-call estimate from prompt text and model registry tokenizer metadata.
- post-call actual usage from provider response, when available.
- fallback estimate when provider usage is missing.

Token records should include:

- tenant context
- workspace context
- prompt version
- model key
- provider key
- input tokens
- output tokens
- total tokens
- estimate vs actual flag
- request/response correlation ID

## 13. Cost Tracking Hooks

Cost tracking should use model registry pricing.

Cost records should include:

- input token unit cost
- output token unit cost
- currency
- calculated cost in minor units
- provider-reported cost if available
- billing period metadata later

Cost tracking must not become billing logic in this task family. Billing remains out of MVP foundation scope unless explicitly approved.

## 14. Error Handling

Provider errors should normalize into framework error classes:

- `ProviderConfigurationError`
- `ProviderAuthenticationError`
- `ProviderRateLimitError`
- `ProviderQuotaError`
- `ProviderTimeoutError`
- `ProviderTransientError`
- `ProviderSafetyError`
- `ProviderValidationError`
- `ProviderResponseError`
- `ProviderUnavailableError`

API-facing errors should be safe and should not expose provider secrets, raw request bodies, stack traces, or hidden prompts.

Internal logs may include provider error codes and sanitized correlation IDs.

## 15. Provider Health Checks

Providers should expose health checks that can run without sending tenant data.

Health check levels:

- configuration present
- credentials available
- provider endpoint reachable
- model/deployment available
- optional low-cost completion probe in non-production or admin-triggered contexts

Health results should include:

- provider key
- model key or deployment
- status
- latency
- checked_at
- safe error code

Health checks must avoid logging secrets or prompt content.

## 16. Tenant-Level Model Configuration Future

Future tenant configuration should support:

- default organisation model
- workspace override model
- allowed model list
- disabled provider list
- monthly token or cost caps
- data residency requirements
- provider opt-in/opt-out
- fallback provider policy

Tenant-level configuration must be enforced before provider calls are made, not after.

## 17. Security and Secrets Handling

Secrets must be handled through environment variables or a secret manager, never committed to code or docs.

Security requirements:

- no API keys in repository files.
- no provider secrets in logs.
- no raw prompts in broad application logs by default.
- tenant IDs included in internal audit/usage records.
- prompt content logging disabled unless explicitly enabled for secure debugging.
- provider metadata sanitized before returning API responses.
- tenant data must never be sent to a provider disallowed by tenant policy.

## 18. Observability and Logging

Observability should include:

- provider key
- model key
- prompt version
- tenant/workspace IDs
- latency
- retries
- timeout flags
- token usage
- estimated cost
- finish reason
- fallback usage
- citation count
- context block count
- error class

Logs should be structured and correlation-ID based. Prompt and retrieved context content should not be logged by default.

## 19. Edge Cases

The framework should handle:

- empty retrieval context.
- prompt too large for model context window.
- model disabled or deprecated.
- provider credentials missing.
- provider rate limit or quota exceeded.
- provider timeout after partial generation.
- malformed provider response.
- provider returns answer without usage metadata.
- provider safety refusal.
- tenant policy disallows selected provider.
- stream interrupted by client disconnect.
- retry succeeds after transient failure.
- retry would duplicate cost and should be limited.
- prompt version unknown or disabled.
- JSON/tool features requested for unsupported model.

## 20. Acceptance Criteria

Future implementation tasks should satisfy:

- Provider interface exists and is unit tested.
- Mock provider exists and is deterministic.
- OpenAI-compatible provider can be configured without hardcoded secrets.
- Model registry can resolve provider/model metadata.
- Prompt version is captured in requests and responses.
- Provider routing enforces defaults and future tenant restrictions.
- Safe error normalization exists.
- Timeout and retry policy is centralized.
- Token and cost hooks exist even if billing is not implemented.
- Provider calls are observable without logging secrets or raw prompts by default.
- Tenant isolation is preserved from retrieval through answer generation.

## 21. Future Implementation Tasks

Recommended follow-on tasks:

1. `TASK-040-ai-provider-interface-and-mock-provider.md` — implement provider interfaces, request/response schemas, deterministic mock provider, and tests.
2. `TASK-041-model-and-prompt-registry-foundation.md` — implement code/config registries for model and prompt metadata.
3. `TASK-042-openai-compatible-provider-adapter.md` — implement OpenAI-compatible non-streaming provider behind feature/config flags.
4. `TASK-043-ai-answer-generation-service.md` — combine TASK-038 prompt output with provider completion and citation-preserving response objects.
5. `TASK-044-ai-usage-token-cost-logging.md` — persist token, latency, and estimated cost records.
6. `TASK-045-provider-health-check-api.md` — add admin/internal provider health checks.
7. `TASK-046-streaming-answer-design-and-api.md` — implement provider-normalized streaming events.
8. `TASK-047-tenant-model-configuration-foundation.md` — add future organisation/workspace model policy controls.
9. `TASK-048-json-mode-and-tool-call-compatibility.md` — add structured-output and tool-call request compatibility without executing tools by default.
