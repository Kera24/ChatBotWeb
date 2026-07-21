# AI Core Local Development

The AI Core module provides the first provider-neutral generation foundation for local development and tests. It does not connect to any real LLM provider.

## Module Layout

- `apps/api/app/ai/contracts.py` defines provider-neutral request, response, message, token usage, provider metadata, and finish reason models.
- `apps/api/app/ai/errors.py` defines structured AI Core and provider errors.
- `apps/api/app/ai/providers/base.py` defines the abstract provider interface and provider health/capability metadata.
- `apps/api/app/ai/providers/mock.py` implements the deterministic local mock provider.
- `apps/api/app/ai/provider_registry.py` registers and resolves providers by provider key.
- `apps/api/app/ai/model_registry.py` registers and resolves in-memory MVP model configuration.
- `apps/api/app/ai/prompt_registry.py` registers prompt definitions and immutable prompt versions.
- `apps/api/app/ai/service.py` coordinates prompt rendering, model resolution, provider execution, token usage, latency, and metadata.
- `apps/api/app/ai/dependencies.py` explicitly creates the AI Core container used by FastAPI app state.
- `apps/api/app/api/v1/ai.py` exposes the internal development-only generation endpoint.

## Provider-Neutral Architecture

The API layer and AI Core service communicate through provider-neutral contracts. `AIRequest` contains rendered system and user messages, prompt metadata, model metadata, optional tenant scope, timeout input, and request metadata. `AIResponse` returns generated text, provider and model identifiers, prompt version/hash metadata, token usage, latency, finish reason, and provider metadata.

No provider-specific SDK classes are imported by these contracts.

## Mock Provider Behaviour

The default provider key is `mock`. The default model key is `mock-grounded-answer`.

The mock provider:

- Performs no network calls.
- Uses no randomness.
- Produces the same output for the same rendered prompt.
- Prefixes generated text with a stable `[mock:<digest>]` marker.
- Estimates tokens with a simple stable word-count approximation.
- Supports `simulate_failure` for safe provider failure testing.
- Supports `simulate_timeout` for safe timeout testing.
- Returns provider metadata indicating deterministic local execution and no network access.

## Internal Endpoint

`POST /api/v1/ai/generate` is a development/internal-only endpoint for validating AI Core plumbing. It is restricted to `super_admin` through the existing temporary development RBAC headers.

This is not a public chat endpoint. It does not perform retrieval, RAG orchestration, chat persistence, message storage, billing, or analytics.

### Request

```json
{
  "prompt_key": "grounded_rag_answer",
  "model_key": "mock-grounded-answer",
  "variables": {
    "question": "What is Yoranix?",
    "context": "[1] Yoranix is a source-grounded AI platform."
  }
}
```

Use development headers:

```http
X-Development-User-Email: super@example.test
X-Development-Role: super_admin
```

### Response

```json
{
  "success": true,
  "data": {
    "text": "[mock:<digest>] Deterministic mock response for prompt grounded_rag_answer@v1.",
    "provider_key": "mock",
    "model_key": "mock-grounded-answer",
    "provider_model_name": "mock-local-v1",
    "prompt_key": "grounded_rag_answer",
    "prompt_version": "v1",
    "prompt_hash": "<stable-hash>",
    "token_usage": {
      "input_tokens": 32,
      "output_tokens": 8,
      "total_tokens": 40,
      "estimated": true
    },
    "latency_ms": 0,
    "finish_reason": "stop"
  }
}
```

## Configuration

Local AI Core settings are defined in `apps/api/app/core/config.py`:

- `DEFAULT_AI_PROVIDER_KEY`
- `DEFAULT_AI_MODEL_KEY`
- `AI_REQUEST_TIMEOUT_SECONDS`
- `MOCK_PROVIDER_FAILURE_MODE`

No real provider API keys are required or supported by TASK-046.

## Test Commands

Run API tests:

```bash
npm run api:test
```

Run full verification if available:

```bash
npm run verify
```

## Warning

No real AI provider is connected. The current implementation is intentionally local, deterministic, and safe for development and automated tests only.
