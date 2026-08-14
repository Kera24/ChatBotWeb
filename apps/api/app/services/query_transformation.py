"""Provider-independent retrieval query transformation abstraction (Retrieval
V2 Phase 3, docs/future/QueryRewrite.md) - a pre-retrieval step that turns the
user's original question into a small set of retrieval-oriented query
strings, mirroring `app.services.reranking`'s shape (`QueryTransformer`
protocol + dataclass implementations + `build_query_transformer` factory) so
`RAGOrchestrator`/`assemble_retrieval_context` never couple to a specific
rewrite provider/model.

Three implementations ship today:
  - `IdentityQueryTransformer` ("identity"): exact current behaviour - one
    retrieval query, the original question, untouched. The production
    default and the one-line rollback target (QUERY_TRANSFORMER_PROVIDER=identity).
  - `DeterministicQueryTransformer` ("deterministic"): no LLM - conversational
    filler stripping and small acronym/abbreviation expansion, entirely
    local and free.
  - `ModelAssistedQueryTransformer` ("model_assisted"): a concise,
    search-oriented reformulation produced by the existing
    AICoreService/AIProvider abstraction (see `app.ai.dependencies` for the
    adapter that wires a real `generate` callable in) - this module never
    imports `app.ai.*` directly, so it never couples to OpenRouter/Ollama/a
    specific LLM (see this module's Part 2 requirement in
    docs/future/QueryRewrite.md).

Hard requirement (original-question immutability): nothing in this module
ever replaces `RAGOrchestrationRequest.query` - it only ever produces
ADDITIONAL retrieval-only query strings alongside the original, which
`RetrievalQueryPlan.retrieval_queries[0]` always is. Callers (RAGOrchestrator)
must keep using the original question for generation, guardrails, evidence
sufficiency, conversation history, and persistence - see
`app.ai.rag_orchestrator.RAGOrchestrator.answer()`.

Failure policy (see `transform_query` below): production traffic falls back
safely to the identity plan (original query only) on any transformer error
(`fail_loud=False`, the default); evaluation runs must pass `fail_loud=True`
so a transformer defect surfaces as a hard case failure instead of silently
"succeeding" via the same fallback - mirrors
`app.services.reranking.rerank_candidates` exactly.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol

from app.services.vector_search import VectorSearchMatch

logger = logging.getLogger(__name__)

IDENTITY_PROVIDER = "identity"
DETERMINISTIC_PROVIDER = "deterministic"
MODEL_ASSISTED_PROVIDER = "model_assisted"

# Part 3 discipline: original + at most one rewrite + at most one alternate.
DEFAULT_MAX_QUERIES = 3
DEFAULT_MAX_QUERY_CHARS = 300


class QueryTransformerError(RuntimeError):
    pass


class QueryTransformerTimeoutError(QueryTransformerError):
    pass


class QueryTransformerUnavailableError(QueryTransformerError):
    pass


class QueryTransformerMalformedOutputError(QueryTransformerError):
    pass


@dataclass(frozen=True)
class RetrievalQueryPlan:
    """The output of one `transform()` call. `retrieval_queries[0]` is always
    `original_query` (deduplicated/normalized set, never empty) - a caller
    that only ever reads `retrieval_queries` and ignores everything else
    reproduces current dense_only behaviour whenever transformation is a
    no-op or disabled."""

    original_query: str
    retrieval_queries: tuple[str, ...]
    extracted_terms: tuple[str, ...]
    transformation_type: str  # "identity" | "deterministic" | "model_assisted"
    provider: str
    model: str
    latency_ms: int
    status: str  # "identity" | "ok" | "unchanged" | "failed" | "timeout" | "malformed_output" | "unavailable" | "empty_rewrite"
    error_message: str | None = None


class QueryTransformer(Protocol):
    provider_name: str
    model_name: str

    def transform(self, *, query: str, context: dict[str, Any] | None = None) -> RetrievalQueryPlan: ...


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _normalise_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _dedup_queries(queries: list[str], *, max_queries: int) -> tuple[str, ...]:
    """Case-insensitive/whitespace-insensitive de-duplication (Part 7) that
    preserves first-seen order and always keeps the first entry (the
    original query) even if a later entry is character-identical after
    normalisation. Truncates to `max_queries` deterministically (earlier
    entries - original, then rewrite, then alternate - always win)."""
    seen: set[str] = set()
    deduped: list[str] = []
    for candidate in queries:
        normalised = _normalise_whitespace(candidate)
        if not normalised:
            continue
        key = normalised.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalised)
    return tuple(deduped[: max(max_queries, 1)])


@dataclass(frozen=True)
class IdentityQueryTransformer:
    """Identity pass-through - the production default
    (QUERY_TRANSFORMER_PROVIDER=identity) and the reference behaviour every
    other implementation's fallback path reproduces on failure."""

    provider_name: str = IDENTITY_PROVIDER
    model_name: str = "none"

    def transform(self, *, query: str, context: dict[str, Any] | None = None) -> RetrievalQueryPlan:
        started_at = perf_counter()
        normalised = _normalise_whitespace(query)
        return RetrievalQueryPlan(
            original_query=query,
            retrieval_queries=(normalised or query,),
            extracted_terms=(),
            transformation_type=IDENTITY_PROVIDER,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=_elapsed_ms(started_at),
            status="identity",
        )


# Small, generic, domain-agnostic abbreviation table - deliberately not
# tuned to any one evaluation corpus (that would be overfitting a "generic
# normalization" strategy to a specific test set, defeating the point of
# measuring it honestly). Whole-word, case-insensitive matches only.
_DETERMINISTIC_ABBREVIATIONS: dict[str, str] = {
    "api": "application programming interface",
    "sla": "service level agreement",
    "faq": "frequently asked questions",
    "sso": "single sign-on",
    "config": "configuration",
    "configs": "configurations",
    "auth": "authentication",
    "admin": "administrator",
    "repo": "repository",
    "env": "environment",
    "prod": "production",
    "docs": "documentation",
    "app": "application",
    "id": "identifier",
    "max": "maximum",
    "min": "minimum",
    "eta": "estimated time of arrival",
    "ci/cd": "continuous integration continuous deployment",
}

# Conversational-to-canonical wording (Part 1 mismatch category): stripped
# from the START of the query only, so the remaining text stays a faithful,
# un-truncated statement of what's being asked - never removes words from
# the middle/end of a question.
_CONVERSATIONAL_PREFIXES = [
    r"^can you (please )?tell me\s+",
    r"^could you (please )?(explain|tell me)\s+",
    r"^i (want|need|would like) to know\s+",
    r"^i'?m (trying to find out|wondering)\s+",
    r"^do you know\s+",
    r"^please (tell me|explain)\s+",
]


@dataclass(frozen=True)
class DeterministicQueryTransformer:
    """No LLM - safe, local normalization/term extraction (Part 3.2):
    conversational-filler stripping and whole-word abbreviation expansion.
    Never invents content; only ever removes filler or substitutes a
    well-known expansion for its abbreviation."""

    provider_name: str = DETERMINISTIC_PROVIDER
    model_name: str = "builtin"
    abbreviations: dict[str, str] = field(default_factory=lambda: dict(_DETERMINISTIC_ABBREVIATIONS))
    max_queries: int = DEFAULT_MAX_QUERIES

    def transform(self, *, query: str, context: dict[str, Any] | None = None) -> RetrievalQueryPlan:
        started_at = perf_counter()
        normalised = _normalise_whitespace(query)

        canonical = normalised
        for pattern in _CONVERSATIONAL_PREFIXES:
            stripped = re.sub(pattern, "", canonical, flags=re.IGNORECASE)
            if stripped != canonical:
                canonical = _normalise_whitespace(stripped)
                break

        extracted_terms: list[str] = []
        expanded = canonical

        def _expand(match: re.Match[str]) -> str:
            word = match.group(0)
            expansion = self.abbreviations.get(word.lower())
            if expansion is None:
                return word
            extracted_terms.append(expansion)
            return expansion

        expanded = re.sub(r"[A-Za-z][A-Za-z/]*", _expand, expanded)
        expanded = _normalise_whitespace(expanded)

        retrieval_queries = [normalised]
        if canonical.lower() != normalised.lower():
            retrieval_queries.append(canonical)
        if expanded.lower() not in {q.lower() for q in retrieval_queries}:
            retrieval_queries.append(expanded)

        changed = len(retrieval_queries) > 1
        return RetrievalQueryPlan(
            original_query=query,
            retrieval_queries=_dedup_queries(retrieval_queries, max_queries=self.max_queries),
            extracted_terms=tuple(dict.fromkeys(extracted_terms)),
            transformation_type=DETERMINISTIC_PROVIDER,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=_elapsed_ms(started_at),
            status="ok" if changed else "unchanged",
        )


class QueryRewriteGenerator(Protocol):
    """Minimal seam between this module and the existing AI provider
    abstraction - deliberately NOT `app.ai.service.AICoreService` itself, so
    `app.services.query_transformation` stays provider-independent (Part 2).
    A caller (e.g. `app.ai.dependencies.build_query_rewrite_generate_fn`)
    supplies a closure that wraps `AICoreService.generate()`; this module
    only ever sees plain text in, plain text out."""

    def __call__(self, *, query: str) -> str: ...


_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _parse_model_rewrite_output(raw_text: str, *, max_query_chars: int) -> tuple[str, str | None, list[str]]:
    """Strict-ish JSON parsing of the model-assisted rewrite output (Part 5:
    "output strict structured data"). Tolerates the model wrapping the JSON
    object in prose/code fences (extracts the first `{...}` span) but never
    tolerates a genuinely malformed/missing schema - that raises
    `QueryTransformerMalformedOutputError` so `transform_query`'s
    fail-safe/fail-loud policy applies uniformly."""
    match = _JSON_OBJECT_PATTERN.search(raw_text)
    if match is None:
        raise QueryTransformerMalformedOutputError("Model rewrite output did not contain a JSON object.")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise QueryTransformerMalformedOutputError(f"Model rewrite output was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise QueryTransformerMalformedOutputError("Model rewrite output JSON was not an object.")

    rewritten = payload.get("rewritten_query")
    if not isinstance(rewritten, str):
        raise QueryTransformerMalformedOutputError("Model rewrite output missing string field 'rewritten_query'.")
    rewritten = _normalise_whitespace(rewritten)
    if len(rewritten) > max_query_chars:
        raise QueryTransformerMalformedOutputError(
            f"Model rewrite 'rewritten_query' exceeds QUERY_TRANSFORMER_MAX_QUERY_CHARS ({len(rewritten)} > {max_query_chars})."
        )

    alternate = payload.get("alternate_query")
    if alternate is not None:
        if not isinstance(alternate, str):
            raise QueryTransformerMalformedOutputError("Model rewrite output field 'alternate_query' must be a string or null.")
        alternate = _normalise_whitespace(alternate)
        if len(alternate) > max_query_chars:
            raise QueryTransformerMalformedOutputError(
                f"Model rewrite 'alternate_query' exceeds QUERY_TRANSFORMER_MAX_QUERY_CHARS ({len(alternate)} > {max_query_chars})."
            )
        if not alternate:
            alternate = None

    extracted_terms_raw = payload.get("extracted_terms") or []
    if not isinstance(extracted_terms_raw, list) or not all(isinstance(term, str) for term in extracted_terms_raw):
        raise QueryTransformerMalformedOutputError("Model rewrite output field 'extracted_terms' must be a list of strings.")

    return rewritten, alternate, [_normalise_whitespace(term) for term in extracted_terms_raw if term.strip()]


def _run_with_timeout(fn, *, timeout_seconds: float) -> Any:
    # Deliberately NOT a `with ThreadPoolExecutor(...) as pool:` block - that
    # context manager's __exit__ calls shutdown(wait=True), which blocks
    # until the submitted call actually finishes even after the
    # future.result(timeout=...) below has already raised. That would make
    # the real wall-clock cost of a slow/hanging generate() call
    # max(timeout_seconds, actual completion time) instead of
    # timeout_seconds - silently defeating the whole point of a timeout and
    # the Part 8 "production must continue safely" guarantee. shutdown(wait=
    # False) here lets this call return within timeout_seconds regardless of
    # how long the orphaned background call keeps running - Python cannot
    # forcibly kill a thread, so the underlying call is abandoned, not
    # cancelled, but the caller is never blocked on it.
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as exc:
        raise QueryTransformerTimeoutError(f"Query rewrite call did not complete within {timeout_seconds}s.") from exc
    finally:
        pool.shutdown(wait=False)


@dataclass
class ModelAssistedQueryTransformer:
    """A concise, search-oriented reformulation produced by whatever
    generation provider/model `generate` is bound to (see
    `app.ai.dependencies.build_query_rewrite_generate_fn`) - reuses the
    existing AICoreService/AIProvider abstraction rather than introducing a
    new provider (Part 5 requirement).

    The prompt this is paired with (`retrieval_query_rewrite`, see
    `app.ai.prompt_registry.register_default_query_rewrite_prompt`)
    instructs the model to preserve meaning, never answer the question,
    never invent entities, and treat the user's question as untrusted data
    it must not follow instructions from - the same "untrusted data" framing
    already used for retrieved document content
    (`app.ai.prompt_registry.register_default_grounded_rag_prompt`). Because
    this transformer's output is only ever used as a retrieval-query string
    (never executed, never interpolated into SQL/shell/templates), there is
    no further injection surface downstream even if a rewrite were somehow
    influenced by adversarial input - see docs/future/QueryRewrite.md Part 5.
    """

    generate: QueryRewriteGenerator
    model_name: str
    provider_name: str = MODEL_ASSISTED_PROVIDER
    timeout_seconds: float = 3.0
    max_query_chars: int = DEFAULT_MAX_QUERY_CHARS
    max_queries: int = DEFAULT_MAX_QUERIES

    def transform(self, *, query: str, context: dict[str, Any] | None = None) -> RetrievalQueryPlan:
        started_at = perf_counter()
        normalised = _normalise_whitespace(query)
        if not normalised:
            return RetrievalQueryPlan(
                original_query=query,
                retrieval_queries=(query,),
                extracted_terms=(),
                transformation_type=MODEL_ASSISTED_PROVIDER,
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=_elapsed_ms(started_at),
                status="empty_rewrite",
            )

        try:
            raw_text = _run_with_timeout(lambda: self.generate(query=normalised), timeout_seconds=self.timeout_seconds)
        except QueryTransformerTimeoutError:
            raise
        except Exception as exc:
            raise QueryTransformerUnavailableError(f"Model-assisted query rewrite call failed: {exc}") from exc

        if not raw_text or not raw_text.strip():
            return RetrievalQueryPlan(
                original_query=query,
                retrieval_queries=(normalised,),
                extracted_terms=(),
                transformation_type=MODEL_ASSISTED_PROVIDER,
                provider=self.provider_name,
                model=self.model_name,
                latency_ms=_elapsed_ms(started_at),
                status="empty_rewrite",
            )

        rewritten, alternate, extracted_terms = _parse_model_rewrite_output(raw_text, max_query_chars=self.max_query_chars)

        retrieval_queries = [normalised]
        status = "unchanged"
        if rewritten and rewritten.lower() != normalised.lower():
            retrieval_queries.append(rewritten)
            status = "ok"
        elif not rewritten:
            status = "empty_rewrite"
        if alternate and alternate.lower() not in {q.lower() for q in retrieval_queries}:
            retrieval_queries.append(alternate)
            status = "ok"

        return RetrievalQueryPlan(
            original_query=query,
            retrieval_queries=_dedup_queries(retrieval_queries, max_queries=self.max_queries),
            extracted_terms=tuple(dict.fromkeys(extracted_terms)),
            transformation_type=MODEL_ASSISTED_PROVIDER,
            provider=self.provider_name,
            model=self.model_name,
            latency_ms=_elapsed_ms(started_at),
            status=status,
        )


def build_query_transformer(
    *,
    provider_name: str,
    model_name: str = "",
    timeout_seconds: float | None = None,
    generate_fn: QueryRewriteGenerator | None = None,
    max_query_chars: int = DEFAULT_MAX_QUERY_CHARS,
    max_queries: int = DEFAULT_MAX_QUERIES,
) -> QueryTransformer:
    # Part 7 hard cap (settings.QUERY_TRANSFORMER_MAX_QUERIES): must be at
    # least 1 (the original query itself is never dropped) - a
    # non-positive/absurd override is clamped rather than silently producing
    # zero retrieval queries.
    effective_max_queries = max(max_queries, 1)
    if provider_name == IDENTITY_PROVIDER:
        return IdentityQueryTransformer()
    if provider_name == DETERMINISTIC_PROVIDER:
        return DeterministicQueryTransformer(max_queries=effective_max_queries)
    if provider_name == MODEL_ASSISTED_PROVIDER:
        if generate_fn is None:
            raise QueryTransformerError(
                "provider_name='model_assisted' requires an explicit generate_fn (see "
                "app.ai.dependencies.build_query_rewrite_generate_fn) - no default generation callable is "
                "assumed here so configuration stays explicit."
            )
        if not model_name:
            raise QueryTransformerError("provider_name='model_assisted' requires an explicit model_name (set QUERY_TRANSFORMER_MODEL_KEY).")
        return ModelAssistedQueryTransformer(
            generate=generate_fn,
            model_name=model_name,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else 3.0,
            max_query_chars=max_query_chars,
            max_queries=effective_max_queries,
        )
    raise QueryTransformerError(f"Unsupported query transformer provider: {provider_name!r}")


def transform_query(
    transformer: QueryTransformer,
    *,
    query: str,
    context: dict[str, Any] | None = None,
    fail_loud: bool = False,
) -> RetrievalQueryPlan:
    """The single call site every retrieval-pipeline caller should use
    instead of `transformer.transform()` directly - applies the
    fail-loud/fail-safe policy split described in this module's docstring.
    `IdentityQueryTransformer` never needs the try/except (it cannot fail),
    so it is also the cheap early-exit path when transformation is
    disabled."""
    if isinstance(transformer, IdentityQueryTransformer):
        return transformer.transform(query=query, context=context)

    started_at = perf_counter()
    try:
        return transformer.transform(query=query, context=context)
    except Exception as exc:
        if fail_loud:
            raise
        logger.warning(
            "Query transformer %s/%s failed, falling back to the original query only: %s",
            transformer.provider_name, transformer.model_name, exc,
        )
        return RetrievalQueryPlan(
            original_query=query,
            retrieval_queries=(_normalise_whitespace(query) or query,),
            extracted_terms=(),
            transformation_type=getattr(transformer, "provider_name", "unknown"),
            provider=getattr(transformer, "provider_name", "unknown"),
            model=getattr(transformer, "model_name", "unknown"),
            latency_ms=_elapsed_ms(started_at),
            status="failed",
            error_message=str(exc),
        )


@dataclass(frozen=True)
class MergedCandidate:
    """One chunk's merged multi-query retrieval outcome (Part 6). `match`
    always carries the dense cosine-similarity score for the query that
    scored it highest (`best_score`, same 0-1 cosine scale evidence
    sufficiency is calibrated for - never an incomparable fused score)."""

    match: VectorSearchMatch
    best_score: float
    matched_query_indices: tuple[int, ...]
    appearances: int
    best_rank: int


@dataclass(frozen=True)
class MergeResult:
    candidates: list[MergedCandidate]
    total_raw_candidate_count: int
    deduplicated_candidate_count: int


def merge_multi_query_candidates(*, per_query_matches: list[list[VectorSearchMatch]], top_k: int) -> MergeResult:
    """Deterministic, explainable merge (Part 6) - never a blind
    concatenation of Top-K lists. For each distinct chunk seen across any
    retrieval query, keeps the match with the highest dense cosine-similarity
    score (a comparable, same-scale value across queries since every query
    ran through the identical dense search path) and records which query
    indices found it, how many times, and its best (lowest-numbered) rank
    within any single query's results.

    Ordering: best_score descending, then appearances descending (a chunk
    multiple queries agree on ranks above one only one query found, all else
    equal), then best_rank ascending, then first-seen order - fully
    deterministic, no randomness, no ties broken by chunk_id/hash."""
    total_raw_candidate_count = 0
    order_index = 0
    by_chunk: dict[str, dict[str, Any]] = {}

    for query_index, matches in enumerate(per_query_matches):
        for rank, match in enumerate(matches, start=1):
            total_raw_candidate_count += 1
            entry = by_chunk.get(match.chunk_id)
            if entry is None:
                by_chunk[match.chunk_id] = {
                    "match": match,
                    "best_score": match.score,
                    "matched_query_indices": {query_index},
                    "appearances": 1,
                    "best_rank": rank,
                    "order_index": order_index,
                }
                order_index += 1
            else:
                entry["matched_query_indices"].add(query_index)
                entry["appearances"] += 1
                if match.score > entry["best_score"]:
                    entry["match"] = match
                    entry["best_score"] = match.score
                if rank < entry["best_rank"]:
                    entry["best_rank"] = rank

    merged = [
        MergedCandidate(
            match=entry["match"],
            best_score=entry["best_score"],
            matched_query_indices=tuple(sorted(entry["matched_query_indices"])),
            appearances=entry["appearances"],
            best_rank=entry["best_rank"],
        )
        for entry in by_chunk.values()
    ]
    order_lookup = {entry["match"].chunk_id: entry["order_index"] for entry in by_chunk.values()}
    merged.sort(key=lambda c: (-c.best_score, -c.appearances, c.best_rank, order_lookup[c.match.chunk_id]))

    return MergeResult(
        candidates=merged[: max(top_k, 0)],
        total_raw_candidate_count=total_raw_candidate_count,
        deduplicated_candidate_count=len(by_chunk),
    )
