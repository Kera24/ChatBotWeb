"""Tests for the real local Ollama embedding provider.

Deterministic tests (always run, no Ollama required) cover configuration
validation and the "no silent fallback to mock" guarantee. Live tests
(skipped cleanly, not failed, when no local Ollama runtime is reachable)
exercise the real HTTP call and the semantic-separation property that makes a
similarity threshold meaningful at all.
"""

from __future__ import annotations

import httpx
import pytest

from app.evaluation.embedding_config import (
    EvalEmbeddingConfig,
    EvalEmbeddingNotConfiguredError,
    build_real_eval_embedding_provider,
    load_eval_embedding_config_from_env,
)
from app.services.embeddings import EmbeddingProviderError, OllamaEmbeddingProvider, build_embedding_provider, check_ollama_embedding_model_available

_OLLAMA_BASE_URL = "http://localhost:11434"


def _ollama_reachable() -> bool:
    try:
        response = httpx.get(f"{_OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def _configured_embedding_model() -> str | None:
    """Returns the first installed model with an 'embedding' capability, or
    None if Ollama is unreachable or none is installed. Used only to make the
    live tests self-configuring on whatever machine runs them, rather than
    hardcoding a model name the task explicitly warned against assuming."""
    try:
        response = httpx.get(f"{_OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    for model in response.json().get("models", []):
        if "embedding" in model.get("capabilities", []):
            return model.get("name", "").split(":", 1)[0]
    return None


requires_ollama = pytest.mark.skipif(not _ollama_reachable(), reason="No local Ollama runtime reachable at http://localhost:11434 - skipping live embedding tests.")


# --- deterministic tests: no network required -------------------------------


def test_build_embedding_provider_ollama_requires_explicit_model_name() -> None:
    with pytest.raises(EmbeddingProviderError, match="requires an explicit model_name"):
        build_embedding_provider(provider_name="ollama", model_name="", dimension=768)


def test_load_eval_embedding_config_from_env_defaults_to_local_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ["EVAL_EMBEDDING_PROVIDER", "EVAL_EMBEDDING_MODEL", "EVAL_EMBEDDING_BASE_URL", "EVAL_EMBEDDING_DIMENSION"]:
        monkeypatch.delenv(name, raising=False)
    config = load_eval_embedding_config_from_env()
    assert config.provider == "local-mock"
    assert config.model is None


def test_build_real_eval_embedding_provider_refuses_local_mock_configuration() -> None:
    """A real-evaluation entry point must never silently proceed with the
    mock provider - this is the core "no silent fallback" guarantee."""
    config = EvalEmbeddingConfig(provider="local-mock", model=None, base_url="http://localhost:11434", dimension=768)
    with pytest.raises(EvalEmbeddingNotConfiguredError, match="requires EVAL_EMBEDDING_PROVIDER"):
        build_real_eval_embedding_provider(config)


def test_build_real_eval_embedding_provider_requires_explicit_model() -> None:
    config = EvalEmbeddingConfig(provider="ollama", model=None, base_url="http://localhost:11434", dimension=768)
    with pytest.raises(EvalEmbeddingNotConfiguredError, match="requires EVAL_EMBEDDING_MODEL"):
        build_real_eval_embedding_provider(config)


def test_check_ollama_embedding_model_available_fails_clearly_when_runtime_unreachable() -> None:
    with pytest.raises(EmbeddingProviderError, match="Could not reach Ollama"):
        check_ollama_embedding_model_available(base_url="http://localhost:1", model_name="whatever", timeout_seconds=1.0)


def test_ollama_provider_embed_fails_clearly_when_runtime_unreachable() -> None:
    provider = OllamaEmbeddingProvider(dimension=768, model_name="whatever", base_url="http://localhost:1", timeout_seconds=1.0)
    with pytest.raises(EmbeddingProviderError, match="Could not reach Ollama"):
        provider.embed("test")


# --- live tests: skipped cleanly (not failed) if Ollama is unavailable ------


@requires_ollama
def test_ollama_provider_returns_vector_of_configured_dimension() -> None:
    model_name = _configured_embedding_model()
    if model_name is None:
        pytest.skip("No embedding-capable model installed in the local Ollama runtime.")
    check_ollama_embedding_model_available(base_url=_OLLAMA_BASE_URL, model_name=model_name)
    provider = build_embedding_provider(provider_name="ollama", model_name=model_name, dimension=_probe_dimension(model_name), base_url=_OLLAMA_BASE_URL)
    vector = provider.embed("test query")
    assert len(vector) == provider.dimension
    assert all(isinstance(value, float) for value in vector)


@requires_ollama
def test_ollama_provider_fails_clearly_on_dimension_mismatch() -> None:
    model_name = _configured_embedding_model()
    if model_name is None:
        pytest.skip("No embedding-capable model installed in the local Ollama runtime.")
    provider = build_embedding_provider(provider_name="ollama", model_name=model_name, dimension=1, base_url=_OLLAMA_BASE_URL)
    with pytest.raises(EmbeddingProviderError, match="dimension"):
        provider.embed("test query")


@requires_ollama
def test_ollama_provider_preserves_semantic_similarity_direction() -> None:
    """The property the mock provider lacks and this whole real-embedding
    cycle depends on: a query's similarity to its genuinely relevant text
    must be meaningfully higher than to unrelated text."""
    model_name = _configured_embedding_model()
    if model_name is None:
        pytest.skip("No embedding-capable model installed in the local Ollama runtime.")
    dimension = _probe_dimension(model_name)
    provider = build_embedding_provider(provider_name="ollama", model_name=model_name, dimension=dimension, base_url=_OLLAMA_BASE_URL)

    query = provider.embed("How much does the Team plan cost per month?")
    relevant = provider.embed("Team costs $29 per month and includes 1TB of storage.")
    irrelevant = provider.embed("Bucket names must be lowercase alphanumeric characters with hyphens.")

    def cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b)

    assert cosine(query, relevant) > cosine(query, irrelevant)


def _probe_dimension(model_name: str) -> int:
    response = httpx.post(f"{_OLLAMA_BASE_URL}/api/embed", json={"model": model_name, "input": "probe"}, timeout=30.0)
    response.raise_for_status()
    return len(response.json()["embeddings"][0])
