"""Provider-independent reranking abstraction (Retrieval V2 Phase 2,
docs/future/Reranking.md) - a second-pass re-scoring/re-ordering step over an
already-retrieved dense candidate pool, mirroring the
`app.services.embeddings.EmbeddingProvider` provider-abstraction pattern
(`Reranker` protocol + dataclass implementations + `build_reranker` factory)
so `RAGOrchestrator`/`assemble_retrieval_context` never couple to a specific
reranker model.

Two implementations ship today:
  - `NoOpReranker` ("none"): identity pass-through - the production default
    and the one-line rollback target (RERANKER_PROVIDER=none).
  - `CrossEncoderReranker` ("cross_encoder"): a local, self-hosted
    sentence-transformers cross-encoder - see docs/future/Reranking.md for
    the model choice rationale.

Dense cosine-similarity scores are NEVER overwritten by a rerank score -
`RerankedCandidate.match.score` stays the original dense score throughout
(evidence_sufficiency's off-topic threshold and citation scoring are
calibrated against that scale specifically). The rerank score only ever
travels alongside it, on `RerankedCandidate.rerank_score`, for
ordering/observability.

Failure policy (see `rerank_candidates` below): production traffic falls
back safely to unmodified dense ordering on any reranker error
(`fail_loud=False`, the default); evaluation runs must pass `fail_loud=True`
so a reranker defect surfaces as a hard case failure instead of silently
"succeeding" via the same fallback.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol

from app.services.vector_search import VectorSearchMatch

logger = logging.getLogger(__name__)

NO_RERANKER_PROVIDER = "none"
CROSS_ENCODER_PROVIDER = "cross_encoder"


class RerankerError(RuntimeError):
    pass


class RerankerTimeoutError(RerankerError):
    pass


class RerankerUnavailableError(RerankerError):
    pass


class RerankerMalformedOutputError(RerankerError):
    pass


@dataclass(frozen=True)
class RerankedCandidate:
    """One candidate's before/after position - `match.score` is always the
    original dense cosine similarity, untouched by reranking."""

    match: VectorSearchMatch
    dense_score: float
    dense_rank: int
    rerank_score: float | None
    rerank_rank: int


@dataclass(frozen=True)
class RerankOutcome:
    candidates: list[RerankedCandidate]
    status: str  # "ok" | "no_reranker" | "empty_candidates" | "failed"
    provider_name: str
    model_name: str
    latency_ms: int
    error_message: str | None = None


class Reranker(Protocol):
    provider_name: str
    model_name: str

    def rerank(self, *, query: str, candidates: list[VectorSearchMatch], top_k: int) -> RerankOutcome: ...


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _identity_outcome(
    candidates: list[VectorSearchMatch], *, top_k: int, status: str, provider_name: str, model_name: str, latency_ms: int, error_message: str | None = None
) -> RerankOutcome:
    trimmed = candidates[: max(top_k, 0)]
    ranked = [
        RerankedCandidate(match=match, dense_score=match.score, dense_rank=index + 1, rerank_score=None, rerank_rank=index + 1)
        for index, match in enumerate(trimmed)
    ]
    return RerankOutcome(
        candidates=ranked, status=status, provider_name=provider_name, model_name=model_name, latency_ms=latency_ms, error_message=error_message
    )


@dataclass(frozen=True)
class NoOpReranker:
    """Identity pass-through - the production default (RERANKER_PROVIDER=none)
    and the reference behaviour every other implementation's fallback path
    reproduces on failure."""

    provider_name: str = NO_RERANKER_PROVIDER
    model_name: str = "none"

    def rerank(self, *, query: str, candidates: list[VectorSearchMatch], top_k: int) -> RerankOutcome:
        started_at = perf_counter()
        return _identity_outcome(
            candidates, top_k=top_k, status="no_reranker", provider_name=self.provider_name, model_name=self.model_name, latency_ms=_elapsed_ms(started_at)
        )


def _run_with_timeout(fn, *, timeout_seconds: float) -> Any:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            raise RerankerTimeoutError(f"Reranker call did not complete within {timeout_seconds}s.") from exc


@dataclass
class CrossEncoderReranker:
    """A real, local, credential-free cross-encoder reranker backed by
    sentence-transformers (see docs/future/Reranking.md for the model
    selection rationale - default `cross-encoder/ms-marco-MiniLM-L-6-v2`).
    The model is loaded lazily on first use and cached on the instance, since
    construction (dependency wiring) may happen before it's known whether any
    request will actually need reranking.

    Deliberately has NO fallback to identity ordering inside `rerank()`
    itself - like `OllamaEmbeddingProvider.embed`, a caller who explicitly
    asked for cross-encoder reranking must get a clear, actionable error, not
    a silently degraded result. The safe-fallback-to-dense-ordering behaviour
    lives one layer up, in `rerank_candidates`, where it can be switched off
    for evaluation.
    """

    model_name: str
    provider_name: str = CROSS_ENCODER_PROVIDER
    timeout_seconds: float = 5.0
    _model: Any = field(default=None, init=False, repr=False, compare=False)

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RerankerUnavailableError(
                "provider_name='cross_encoder' requires the 'sentence-transformers' package, which is not installed. "
                "Install it (`pip install sentence-transformers`) or set RERANKER_PROVIDER=none to roll back."
            ) from exc
        try:
            model = CrossEncoder(self.model_name)
        except Exception as exc:
            raise RerankerUnavailableError(f"Could not load cross-encoder model {self.model_name!r}: {exc}") from exc
        self._model = model
        return model

    def rerank(self, *, query: str, candidates: list[VectorSearchMatch], top_k: int) -> RerankOutcome:
        started_at = perf_counter()
        if not candidates:
            return _identity_outcome(
                candidates, top_k=top_k, status="empty_candidates", provider_name=self.provider_name, model_name=self.model_name,
                latency_ms=_elapsed_ms(started_at),
            )

        model = self._load_model()
        pairs = [(query, candidate.content) for candidate in candidates]

        try:
            raw_scores = _run_with_timeout(lambda: model.predict(pairs), timeout_seconds=self.timeout_seconds)
        except RerankerTimeoutError:
            raise
        except Exception as exc:
            raise RerankerError(f"Cross-encoder model {self.model_name!r} failed to score candidates: {exc}") from exc

        scores = list(raw_scores)
        if len(scores) != len(candidates):
            raise RerankerMalformedOutputError(
                f"Cross-encoder model {self.model_name!r} returned {len(scores)} scores for {len(candidates)} candidates "
                "(malformed or partial output)."
            )

        order = sorted(range(len(candidates)), key=lambda index: scores[index], reverse=True)[: max(top_k, 0)]
        ranked = [
            RerankedCandidate(
                match=candidates[original_index],
                dense_score=candidates[original_index].score,
                dense_rank=original_index + 1,
                rerank_score=float(scores[original_index]),
                rerank_rank=new_rank + 1,
            )
            for new_rank, original_index in enumerate(order)
        ]
        return RerankOutcome(
            candidates=ranked, status="ok", provider_name=self.provider_name, model_name=self.model_name, latency_ms=_elapsed_ms(started_at)
        )


def build_reranker(*, provider_name: str, model_name: str = "", timeout_seconds: float | None = None) -> Reranker:
    if provider_name == NO_RERANKER_PROVIDER:
        return NoOpReranker()
    if provider_name == CROSS_ENCODER_PROVIDER:
        if not model_name:
            raise RerankerError(
                "provider_name='cross_encoder' requires an explicit model_name (set RERANKER_MODEL) - "
                "no default model is assumed here so configuration stays explicit."
            )
        return CrossEncoderReranker(model_name=model_name, timeout_seconds=timeout_seconds if timeout_seconds is not None else 5.0)
    raise RerankerError(f"Unsupported reranker provider: {provider_name!r}")


def rerank_candidates(
    reranker: Reranker,
    *,
    query: str,
    candidates: list[VectorSearchMatch],
    top_k: int,
    fail_loud: bool = False,
) -> RerankOutcome:
    """The single call site every retrieval-pipeline caller should use
    instead of `reranker.rerank()` directly - applies the fail-loud/fail-safe
    policy split described in this module's docstring. `NoOpReranker` never
    needs the try/except (it cannot fail), so it is also the cheap early-exit
    path when reranking is disabled."""
    if isinstance(reranker, NoOpReranker):
        return reranker.rerank(query=query, candidates=candidates, top_k=top_k)

    started_at = perf_counter()
    try:
        return reranker.rerank(query=query, candidates=candidates, top_k=top_k)
    except Exception as exc:
        if fail_loud:
            raise
        logger.warning(
            "Reranker %s/%s failed, falling back to unmodified dense ordering: %s", reranker.provider_name, reranker.model_name, exc
        )
        fallback = _identity_outcome(
            candidates, top_k=top_k, status="failed", provider_name=reranker.provider_name, model_name=reranker.model_name,
            latency_ms=_elapsed_ms(started_at), error_message=str(exc),
        )
        return fallback
