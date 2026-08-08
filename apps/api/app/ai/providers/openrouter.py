from time import perf_counter

import httpx

from app.ai.contracts import AIRequest, AIResponse, FinishReason, ProviderMetadata, TokenUsage
from app.ai.errors import (
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderInvalidResponseError,
    AIProviderRateLimitedError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.ai.providers.base import AIProvider, ProviderCapabilities

_FINISH_REASON_MAP = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
    "tool_calls": FinishReason.TOOL_CALL,
}
_BODY_EXCERPT_CHARS = 500


class OpenRouterAIProvider(AIProvider):
    """A real generation provider backed by OpenRouter's OpenAI-compatible
    chat-completions API. Unlike MockAIProvider, this makes a genuine network
    call and returns model-generated text - see
    docs/engineering/ai-system-design.md for the provider-abstraction
    contract this must satisfy (AIProvider.generate() raising the
    app.ai.errors.AIProviderError family on failure, never a raw exception).

    Deliberately has NO fallback to the mock provider on any failure -
    generate() always raises a classified AIProviderError with an actionable
    message rather than silently degrading, matching the same "no silent
    fallback" guarantee OllamaEmbeddingProvider already establishes for
    embeddings (see app.services.embeddings).
    """

    provider_key = "openrouter"
    display_name = "OpenRouter"
    capabilities = ProviderCapabilities(streaming=False, json_mode=False, tools=False, vision=False)

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        temperature: float = 0.0,
        max_output_tokens: int = 512,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise AIProviderConfigurationError(
                "OpenRouterAIProvider requires a non-empty api_key. Set OPENROUTER_API_KEY."
            )
        if not model:
            raise AIProviderConfigurationError(
                "OpenRouterAIProvider requires a non-empty model. Set OPENROUTER_MODEL (e.g. 'openai/gpt-4o-mini')."
            )
        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.default_temperature = temperature
        self.default_max_output_tokens = max_output_tokens
        self.default_timeout_seconds = timeout_seconds
        # Optional injected client is test-only (see tests/test_openrouter_provider.py,
        # which binds an httpx.MockTransport) - production always builds a
        # fresh client per call via the module-level httpx.post equivalent.
        self._client = client

    def generate(self, request: AIRequest, *, timeout_seconds: float | None = None) -> AIResponse:
        effective_timeout = timeout_seconds or request.timeout_seconds or self.default_timeout_seconds
        payload = {
            "model": self.model,
            "messages": [{"role": message.role.value, "content": message.content} for message in request.messages],
            # request.temperature/max_output_tokens are not yet meaningfully
            # populated by any caller (AICoreService.generate always leaves
            # them at the AIRequest pydantic defaults) - this provider is
            # configured directly via LLM_TEMPERATURE/LLM_MAX_TOKENS instead
            # of trusting those fields, so behaviour is explicit rather than
            # accidentally always-deterministic/always-512-tokens.
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_output_tokens,
        }
        started_at = perf_counter()
        try:
            response = self._send(payload, timeout_seconds=effective_timeout)
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(f"OpenRouter request timed out after {effective_timeout}s.") from exc
        except httpx.HTTPError as exc:
            raise AIProviderUnavailableError(f"Could not reach OpenRouter at {self.base_url!r}: {exc}") from exc
        latency_ms = int((perf_counter() - started_at) * 1000)

        self._raise_for_status(response)
        return self._parse_response(response, request=request, latency_ms=latency_ms)

    def _send(self, payload: dict, *, timeout_seconds: float) -> httpx.Response:
        # Authorization header is built fresh per call and never attached to
        # any exception, log line, or returned AIResponse/ProviderMetadata -
        # see the "never log the API key" requirement this provider exists
        # under.
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        url = f"{self.base_url}/chat/completions"
        if self._client is not None:
            return self._client.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        return httpx.post(url, json=payload, headers=headers, timeout=timeout_seconds)

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 200:
            return
        if response.status_code in (401, 403):
            raise AIProviderAuthenticationError(
                f"OpenRouter authentication failed (HTTP {response.status_code}). Check OPENROUTER_API_KEY."
            )
        if response.status_code == 429:
            raise AIProviderRateLimitedError("OpenRouter rate limit exceeded (HTTP 429).")
        if response.status_code >= 500:
            raise AIProviderUnavailableError(
                f"OpenRouter returned HTTP {response.status_code} (upstream error): {_body_excerpt(response)}"
            )
        raise AIProviderError(f"OpenRouter returned unexpected HTTP {response.status_code}: {_body_excerpt(response)}")

    def _parse_response(self, response: httpx.Response, *, request: AIRequest, latency_ms: int) -> AIResponse:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AIProviderInvalidResponseError(
                f"OpenRouter returned a non-JSON response: {_body_excerpt(response)}"
            ) from exc

        choices = payload.get("choices")
        if not choices:
            raise AIProviderInvalidResponseError(f"OpenRouter response contained no choices: {_body_excerpt(response)}")

        message = choices[0].get("message") or {}
        text = message.get("content")
        if not text:
            raise AIProviderInvalidResponseError(f"OpenRouter response contained an empty message: {_body_excerpt(response)}")

        raw_finish_reason = choices[0].get("finish_reason")
        finish_reason = _FINISH_REASON_MAP.get(raw_finish_reason, FinishReason.STOP)
        provider_model_name = payload.get("model") or self.model

        usage_payload = payload.get("usage") or {}
        if usage_payload:
            token_usage = TokenUsage(
                input_tokens=int(usage_payload.get("prompt_tokens", 0) or 0),
                output_tokens=int(usage_payload.get("completion_tokens", 0) or 0),
                total_tokens=int(usage_payload.get("total_tokens", 0) or 0),
                estimated=False,
            )
        else:
            # OpenRouter does not guarantee `usage` for every upstream model -
            # fall back to a word-count estimate rather than reporting zero
            # tokens, and mark it estimated so cost/accounting consumers know
            # not to treat it as billing-grade.
            input_tokens = _estimate_tokens("\n".join(entry.content for entry in request.messages))
            output_tokens = _estimate_tokens(text)
            token_usage = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                estimated=True,
            )

        return AIResponse(
            text=text,
            provider_key=self.provider_key,
            model_key=request.model_key,
            provider_model_name=provider_model_name,
            prompt_key=request.prompt_key,
            prompt_version=request.prompt_version,
            prompt_hash=request.prompt_hash,
            token_usage=token_usage,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            provider_metadata=ProviderMetadata(
                provider_key=self.provider_key,
                provider_model_name=provider_model_name,
                response_id=payload.get("id"),
                raw_finish_reason=raw_finish_reason,
                metadata={"network": True},
            ),
            metadata={},
        )


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split())) if text else 0


def _body_excerpt(response: httpx.Response) -> str:
    return response.text[:_BODY_EXCERPT_CHARS]
