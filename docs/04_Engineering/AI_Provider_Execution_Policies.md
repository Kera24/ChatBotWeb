# AI Provider Execution Policies

TASK-048 adds provider-neutral execution hardening for local AI Core development. No real provider SDKs or external network calls are connected.

## Module Layout

- `apps/api/app/ai/execution_policy.py` defines `ProviderExecutionPolicy`.
- `apps/api/app/ai/executor.py` defines `ProviderRetryExecutor` and `ProviderExecutionResult`.
- `apps/api/app/ai/health.py` defines provider health states, snapshots, and the in-memory health service.
- `apps/api/app/ai/providers/base.py` keeps the provider interface provider-neutral.
- `apps/api/app/ai/providers/mock.py` implements deterministic mock generation and health simulation.
- `apps/api/app/ai/service.py` composes prompt/model/provider resolution, execution policy, retries, health updates, and usage accounting.

## Retry Rules

The default execution policy keeps retries intentionally small:

- `max_attempts` defaults to `2`.
- Validation, missing prompt, missing model, and missing provider errors are not retried because they occur before provider execution.
- Non-retryable provider failures stop immediately.
- Timeout and transient provider-unavailable failures are retryable by default.
- Retry exhaustion is reported with stable structured errors such as `AI_PROVIDER_RETRY_EXHAUSTED` or `AI_PROVIDER_TIMEOUT_EXHAUSTED`.
- The final provider error is preserved through stable error code/message metadata and usage accounting.

## Timeout Rules

Timeout is explicit at the AI Core boundary:

- Endpoint dependency reads `AI_REQUEST_TIMEOUT_SECONDS`.
- `ProviderExecutionPolicy.timeout_seconds` controls provider execution.
- `AIRequest.timeout_seconds` carries the timeout into providers.
- Provider interface accepts `timeout_seconds` directly.
- Usage records persist the timeout value used.

The MVP mock provider simulates timeout deterministically; it does not rely on web-server timeouts.

## Health States

Provider health status is represented as:

- `unknown` before a health check or execution update.
- `healthy` after successful health checks or executions.
- `degraded` when a provider reports degraded status.
- `unavailable` after provider failures or unavailable health simulation.

Health snapshots include provider key, checked timestamp, optional latency, message, consecutive failures, last success time, and last failure time.

## Internal Endpoints

All provider execution policy endpoints are internal development endpoints and require temporary `super_admin` RBAC headers.

List providers:

```http
GET /api/v1/ai/providers
X-Development-User-Email: super@example.test
X-Development-Role: super_admin
```

Get current provider health:

```http
GET /api/v1/ai/providers/mock/health
X-Development-User-Email: super@example.test
X-Development-Role: super_admin
```

Run explicit health check:

```http
POST /api/v1/ai/providers/mock/health-check
X-Development-User-Email: super@example.test
X-Development-Role: super_admin
```

## Mock Simulation Options

The mock provider remains deterministic and local-only:

- `simulate_failure` triggers a non-retryable provider failure.
- `simulate_timeout` triggers retryable timeout failures until attempts are exhausted.
- `simulate_transient_failures` fails the first N attempts with provider-unavailable errors, then succeeds if attempts remain.
- `set_health_status()` supports local tests for healthy, degraded, unavailable, and unknown health checks.

## Accounting Metadata

Usage records include retry and health metadata:

- `attempt_count`
- `final_attempt_number`
- `retry_performed`
- `timeout_seconds`
- `provider_health_at_start`
- `provider_health_at_end`

Existing token, cost, provider, model, prompt, latency, finish reason, and outcome fields are preserved.

## Warning

No real provider is connected. TASK-048 hardens execution boundaries around the deterministic mock provider only.
