"""Configuration for the evaluation cycle's *own* choice of embedding
provider - deliberately separate from the app-wide `EMBEDDING_PROVIDER` /
`EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` settings in `app.core.config`, which
control real customer document embedding and must not be affected by running
an evaluation.

Dimension compatibility (see docs/04_Engineering/Evaluation_Real_Embedding_Provider.md
for the full write-up): on SQLite (every evaluation fixture in this repo runs
on SQLite - see app.evaluation.fixtures.loader), the `chunks.embedding_vector`
column compiles to plain TEXT with no fixed width, and retrieval always
recomputes embeddings live from `chunk.content` filtered by an exact
(embedding_provider, embedding_model, embedding_dimension) match - so ANY
dimension works with zero schema change. On PostgreSQL (production), that
column is a hardcoded `vector(1536)` (see app/db/models/chunk.py and
alembic/versions/0003_create_document_chunk_schema.py). A real embedding
model with a different dimension (e.g. the 768-dimension `nomic-embed-text`
family) would need a real, deliberate migration to change that column width
before it could ever be used for production document embedding - this module
and the evaluation cycle it supports never touch that column or that
migration; they only ever run on an isolated SQLite fixture.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv

from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError, build_embedding_provider, check_ollama_embedding_model_available


class EvalEmbeddingNotConfiguredError(EmbeddingProviderError):
    pass


@dataclass(frozen=True)
class EvalEmbeddingConfig:
    provider: str
    model: str | None
    base_url: str
    dimension: int


# Evidence-based RETRIEVAL_MIN_SIMILARITY_SCORE values, one per embedding
# model, derived from the score-distribution + controlled-threshold-experiment
# process documented in docs/04_Engineering/Evaluation_Score_Distribution_Analysis.md
# and Evaluation_Retrieval_Experiments.md. A similarity threshold is only
# meaningful relative to one specific model's score distribution - it is
# never a universal constant. Do not add an entry here for a new model
# without re-running that same analysis; `recommended_min_similarity_score`
# deliberately returns None (not a guess) for any unlisted model.
_VALIDATED_MIN_SIMILARITY_SCORE_BY_MODEL: dict[str, float] = {
    "nomic-embed-text-v2-moe": 0.25,
}


def recommended_min_similarity_score(config: EvalEmbeddingConfig) -> float | None:
    if config.model is None:
        return None
    return _VALIDATED_MIN_SIMILARITY_SCORE_BY_MODEL.get(config.model)


def load_eval_embedding_config_from_env() -> EvalEmbeddingConfig:
    return EvalEmbeddingConfig(
        provider=getenv("EVAL_EMBEDDING_PROVIDER", "local-mock"),
        model=getenv("EVAL_EMBEDDING_MODEL") or None,
        base_url=getenv("EVAL_EMBEDDING_BASE_URL", "http://localhost:11434"),
        dimension=int(getenv("EVAL_EMBEDDING_DIMENSION", "768")),
    )


def build_real_eval_embedding_provider(config: EvalEmbeddingConfig | None = None) -> EmbeddingProvider:
    """Builds the embedding provider for a *real* evaluation run. Never falls
    back to the mock provider - raises `EvalEmbeddingNotConfiguredError`
    immediately and clearly if the configuration is incomplete or the
    runtime/model is unreachable, since a caller who explicitly requested a
    real-embedding run must never silently get mock (meaningless) scores
    back."""
    config = config or load_eval_embedding_config_from_env()
    if config.provider == "local-mock":
        raise EvalEmbeddingNotConfiguredError(
            "A real evaluation run requires EVAL_EMBEDDING_PROVIDER to be set to a real provider (e.g. 'ollama') - "
            "it is currently unset or 'local-mock', which would silently produce meaningless similarity scores."
        )
    if config.provider == "ollama":
        if not config.model:
            raise EvalEmbeddingNotConfiguredError(
                "EVAL_EMBEDDING_PROVIDER=ollama requires EVAL_EMBEDDING_MODEL to be set explicitly - "
                "no model is assumed, since installed models vary by machine. "
                "Check installed embedding models with: curl http://localhost:11434/api/tags"
            )
        check_ollama_embedding_model_available(base_url=config.base_url, model_name=config.model)
    return build_embedding_provider(provider_name=config.provider, model_name=config.model or "", dimension=config.dimension, base_url=config.base_url)
