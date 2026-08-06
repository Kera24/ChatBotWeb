"""Env-var-driven grader provider construction. Mirrors
app.evaluation.embedding_config's pattern exactly: a frozen config
dataclass, a `*_from_env` loader, and a `build_real_*` constructor that
fails clearly (never silently falls back to the mock provider) when a real
grader was requested but is not actually configured/reachable.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv

from app.evaluation.graders.errors import GraderNotConfiguredError
from app.evaluation.graders.ollama_provider import OllamaGraderProvider, check_ollama_grader_model_available
from app.evaluation.graders.provider import GraderProvider, MockGraderProvider


@dataclass(frozen=True)
class EvalGraderConfig:
    provider: str
    model: str | None
    base_url: str
    temperature: float
    max_tokens: int
    timeout_seconds: float


def load_eval_grader_config_from_env() -> EvalGraderConfig:
    return EvalGraderConfig(
        provider=getenv("EVAL_GRADER_PROVIDER", "mock"),
        model=getenv("EVAL_GRADER_MODEL") or None,
        base_url=getenv("EVAL_GRADER_BASE_URL", "http://localhost:11434"),
        temperature=float(getenv("EVAL_GRADER_TEMPERATURE", "0.0")),
        max_tokens=int(getenv("EVAL_GRADER_MAX_TOKENS", "512")),
        timeout_seconds=float(getenv("EVAL_GRADER_TIMEOUT_SECONDS", "60")),
    )


def build_real_eval_grader_provider(config: EvalGraderConfig | None = None) -> GraderProvider:
    """Builds a real (non-mock) grader provider. Raises GraderNotConfiguredError
    immediately - never silently returns a MockGraderProvider - if
    EVAL_GRADER_PROVIDER is unset/mock, or if EVAL_GRADER_MODEL is missing
    for a provider that requires one, or if the requested model is not
    actually installed/reachable."""
    config = config or load_eval_grader_config_from_env()
    if config.provider == "mock":
        raise GraderNotConfiguredError(
            "A real grader run requires EVAL_GRADER_PROVIDER to be set to a real provider (e.g. 'ollama') - "
            "it is currently unset or 'mock', which would silently produce meaningless heuristic scores instead "
            "of a real model judgement."
        )
    if config.provider == "ollama":
        if not config.model:
            raise GraderNotConfiguredError("EVAL_GRADER_PROVIDER=ollama requires EVAL_GRADER_MODEL to be set explicitly - no default grader model is assumed.")
        check_ollama_grader_model_available(base_url=config.base_url, model_name=config.model)
        return OllamaGraderProvider(
            model_name=config.model, base_url=config.base_url, temperature=config.temperature,
            max_tokens=config.max_tokens, timeout_seconds=config.timeout_seconds,
        )
    raise GraderNotConfiguredError(f"Unknown EVAL_GRADER_PROVIDER {config.provider!r} - supported values are 'mock' and 'ollama'.")


def build_mock_grader_provider() -> GraderProvider:
    return MockGraderProvider()
