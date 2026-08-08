"""Tests for the real OpenRouter generation provider (P0-1 of the launch
readiness review: create_ai_core() previously registered MockAIProvider
unconditionally, so every production answer was a deterministic mock
string). Deterministic, no network required - every HTTP interaction is
intercepted via an injected httpx.MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest

from app.ai.contracts import AIMessage, AIRequest, FinishReason, MessageRole
from app.ai.errors import (
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderInvalidResponseError,
    AIProviderRateLimitedError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.ai.providers.openrouter import OpenRouterAIProvider

_FAKE_API_KEY = "".join(("sk-or-v1-", "abcdefghijklmnopqrstuvwx0123456789"))


def _request(**overrides: object) -> AIRequest:
    defaults: dict[str, object] = dict(
        provider_key="openrouter",
        model_key="openrouter-default",
        provider_model_name="openai/gpt-4o-mini",
        prompt_key="grounded_rag_answer",
        prompt_version="v1",
        prompt_hash="hash-abc",
        messages=[
            AIMessage(role=MessageRole.SYSTEM, content="You are a grounded assistant."),
            AIMessage(role=MessageRole.USER, content="What is the refund window?"),
        ],
        timeout_seconds=5.0,
    )
    defaults.update(overrides)
    return AIRequest(**defaults)


def _provider(handler, **overrides: object) -> OpenRouterAIProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    defaults: dict[str, object] = dict(api_key=_FAKE_API_KEY, model="openai/gpt-4o-mini", client=client)
    defaults.update(overrides)
    return OpenRouterAIProvider(**defaults)


def _success_response(*, include_usage: bool = True) -> dict:
    payload = {
        "id": "gen-abc123",
        "model": "openai/gpt-4o-mini",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Refunds are available within 30 days."}, "finish_reason": "stop"}],
    }
    if include_usage:
        payload["usage"] = {"prompt_tokens": 42, "completion_tokens": 9, "total_tokens": 51}
    return payload


# --- construction / configuration validation --------------------------------


def test_missing_api_key_raises_configuration_error() -> None:
    with pytest.raises(AIProviderConfigurationError, match="OPENROUTER_API_KEY"):
        OpenRouterAIProvider(api_key="", model="openai/gpt-4o-mini")


def test_missing_model_raises_configuration_error() -> None:
    with pytest.raises(AIProviderConfigurationError, match="OPENROUTER_MODEL"):
        OpenRouterAIProvider(api_key=_FAKE_API_KEY, model="")


# --- successful generation ---------------------------------------------------


def test_generate_returns_successful_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat/completions"
        return httpx.Response(200, json=_success_response())

    provider = _provider(handler)
    response = provider.generate(_request())

    assert response.text == "Refunds are available within 30 days."
    assert response.provider_key == "openrouter"
    assert response.provider_model_name == "openai/gpt-4o-mini"
    assert response.finish_reason == FinishReason.STOP
    assert response.provider_metadata.response_id == "gen-abc123"
    assert response.latency_ms >= 0


def test_generate_sends_bearer_authorization_header_and_configured_model() -> None:
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200, json=_success_response())

    provider = _provider(handler, model="anthropic/claude-3-haiku")
    provider.generate(_request())

    sent = captured["request"]
    assert sent.headers["authorization"] == f"Bearer {_FAKE_API_KEY}"
    body = json.loads(sent.content)
    assert body["model"] == "anthropic/claude-3-haiku"
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["content"] == "What is the refund window?"


# --- token usage parsing ------------------------------------------------------


def test_generate_parses_real_token_usage_when_returned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_success_response(include_usage=True))

    provider = _provider(handler)
    response = provider.generate(_request())

    assert response.token_usage.input_tokens == 42
    assert response.token_usage.output_tokens == 9
    assert response.token_usage.total_tokens == 51
    assert response.token_usage.estimated is False


def test_generate_estimates_token_usage_when_not_returned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_success_response(include_usage=False))

    provider = _provider(handler)
    response = provider.generate(_request())

    assert response.token_usage.estimated is True
    assert response.token_usage.total_tokens > 0


# --- error classification -----------------------------------------------------


def test_generate_raises_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    provider = _provider(handler)
    with pytest.raises(AIProviderTimeoutError):
        provider.generate(_request())


def test_generate_raises_rate_limited_error_on_429() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    provider = _provider(handler)
    with pytest.raises(AIProviderRateLimitedError):
        provider.generate(_request())


@pytest.mark.parametrize("status_code", [500, 502, 503])
def test_generate_raises_unavailable_error_on_5xx(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="upstream error")

    provider = _provider(handler)
    with pytest.raises(AIProviderUnavailableError):
        provider.generate(_request())


@pytest.mark.parametrize("status_code", [401, 403])
def test_generate_raises_authentication_error(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": {"message": "invalid credentials"}})

    provider = _provider(handler)
    with pytest.raises(AIProviderAuthenticationError):
        provider.generate(_request())


def test_generate_raises_invalid_response_error_on_malformed_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json at all")

    provider = _provider(handler)
    with pytest.raises(AIProviderInvalidResponseError):
        provider.generate(_request())


def test_generate_raises_invalid_response_error_on_missing_choices() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "gen-1", "model": "openai/gpt-4o-mini", "choices": []})

    provider = _provider(handler)
    with pytest.raises(AIProviderInvalidResponseError):
        provider.generate(_request())


def test_generate_raises_invalid_response_error_on_empty_message_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "gen-1", "model": "openai/gpt-4o-mini", "choices": [{"message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}]})

    provider = _provider(handler)
    with pytest.raises(AIProviderInvalidResponseError):
        provider.generate(_request())


# --- secret hygiene ------------------------------------------------------------


def test_error_messages_never_contain_the_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    provider = _provider(handler)
    with pytest.raises(AIProviderAuthenticationError) as excinfo:
        provider.generate(_request())

    assert _FAKE_API_KEY not in str(excinfo.value)
