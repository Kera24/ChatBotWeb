"""Unit tests for app.services.query_transformation - the provider-independent
retrieval query transformation abstraction (Retrieval V2 Phase 3,
docs/future/QueryRewrite.md).

ModelAssistedQueryTransformer is tested against a fake, injected `generate`
callable rather than a real AICoreService/AIProvider (this module is
deliberately decoupled from app.ai.* - see the module docstring) so the
parsing/timeout/malformed-output/failure-handling logic is fully covered
without a live provider dependency.
"""

from __future__ import annotations

import time

import pytest

from app.services.query_transformation import (
    DETERMINISTIC_PROVIDER,
    IDENTITY_PROVIDER,
    MODEL_ASSISTED_PROVIDER,
    DeterministicQueryTransformer,
    IdentityQueryTransformer,
    ModelAssistedQueryTransformer,
    QueryTransformerError,
    QueryTransformerMalformedOutputError,
    QueryTransformerTimeoutError,
    build_query_transformer,
    merge_multi_query_candidates,
    transform_query,
)
from app.services.vector_search import VectorSearchMatch


def _match(chunk_id: str, *, document_id: str | None = None, score: float, content: str = "content") -> VectorSearchMatch:
    return VectorSearchMatch(
        chunk_id=chunk_id,
        document_id=document_id or f"doc-{chunk_id}",
        document_version_id=f"ver-{chunk_id}",
        chunk_index=0,
        content=content,
        score=score,
        source_type="document",
        source_title=f"Title {chunk_id}",
        page_number=None,
        section_title=None,
        heading_path=None,
        metadata_json=None,
    )


class FakeGenerator:
    """Stands in for app.ai.dependencies.build_query_rewrite_generate_fn's
    closure - returns raw text (or raises) for one query."""

    def __init__(self, response: str | None = None, *, raise_error: Exception | None = None, sleep_seconds: float = 0.0):
        self.response = response
        self.raise_error = raise_error
        self.sleep_seconds = sleep_seconds
        self.calls: list[str] = []

    def __call__(self, *, query: str) -> str:
        self.calls.append(query)
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        if self.raise_error is not None:
            raise self.raise_error
        return self.response or ""


# --- IdentityQueryTransformer ---

def test_identity_transformer_returns_only_the_original_query() -> None:
    plan = IdentityQueryTransformer().transform(query="what is the refund policy")
    assert plan.retrieval_queries == ("what is the refund policy",)
    assert plan.original_query == "what is the refund policy"
    assert plan.status == "identity"
    assert plan.transformation_type == IDENTITY_PROVIDER


def test_identity_transformer_normalises_whitespace_only() -> None:
    plan = IdentityQueryTransformer().transform(query="  what   is   the SLA  ")
    assert plan.retrieval_queries == ("what is the SLA",)


# --- DeterministicQueryTransformer ---

def test_deterministic_transformer_strips_conversational_prefix() -> None:
    plan = DeterministicQueryTransformer().transform(query="can you tell me the maximum session length")
    assert plan.original_query == "can you tell me the maximum session length"
    assert plan.retrieval_queries[0] == "can you tell me the maximum session length"
    assert "the maximum session length" in plan.retrieval_queries
    assert plan.status == "ok"


def test_deterministic_transformer_expands_known_abbreviation() -> None:
    plan = DeterministicQueryTransformer().transform(query="what is the SLA for enterprise")
    expanded = [q for q in plan.retrieval_queries if "service level agreement" in q.lower()]
    assert expanded, plan.retrieval_queries
    assert "service level agreement" in plan.extracted_terms


def test_deterministic_transformer_unchanged_query_reports_status_unchanged() -> None:
    plan = DeterministicQueryTransformer().transform(query="what is the maximum idle session timeout")
    assert plan.retrieval_queries == ("what is the maximum idle session timeout",)
    assert plan.status == "unchanged"


def test_deterministic_transformer_never_invents_unrelated_content() -> None:
    plan = DeterministicQueryTransformer().transform(query="what is the pipeline cache expiry")
    for retrieval_query in plan.retrieval_queries:
        # Every produced query is a subset/expansion of the original words -
        # never introduces an unrelated new entity/fact.
        assert "cache" in retrieval_query.lower() or "pipeline" in retrieval_query.lower()


def test_deterministic_transformer_respects_max_queries_cap() -> None:
    plan = DeterministicQueryTransformer().transform(query="can you tell me the api sla config")
    assert len(plan.retrieval_queries) <= 3


# --- ModelAssistedQueryTransformer: parsing, immutability, extracted terms ---

def test_model_assisted_transformer_parses_strict_json() -> None:
    generator = FakeGenerator(response='{"rewritten_query": "session timeout maximum duration", "alternate_query": null, "extracted_terms": ["timeout"]}')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    plan = transformer.transform(query="how long can a session stay idle before logout")
    assert plan.original_query == "how long can a session stay idle before logout"
    assert plan.retrieval_queries[0] == "how long can a session stay idle before logout"
    assert "session timeout maximum duration" in plan.retrieval_queries
    assert plan.extracted_terms == ("timeout",)
    assert plan.status == "ok"
    assert plan.provider == MODEL_ASSISTED_PROVIDER


def test_model_assisted_transformer_tolerates_prose_wrapped_json() -> None:
    generator = FakeGenerator(response='Sure, here is the rewrite:\n{"rewritten_query": "canonical phrasing", "alternate_query": null, "extracted_terms": []}\nDone.')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    plan = transformer.transform(query="original phrasing")
    assert "canonical phrasing" in plan.retrieval_queries


def test_model_assisted_transformer_includes_alternate_query() -> None:
    generator = FakeGenerator(response='{"rewritten_query": "rewrite one", "alternate_query": "rewrite two", "extracted_terms": []}')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    plan = transformer.transform(query="original")
    assert plan.retrieval_queries == ("original", "rewrite one", "rewrite two")


def test_model_assisted_transformer_never_replaces_original_query_field() -> None:
    generator = FakeGenerator(response='{"rewritten_query": "totally different search terms", "alternate_query": null, "extracted_terms": []}')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    plan = transformer.transform(query="what is the original question")
    assert plan.original_query == "what is the original question"
    assert plan.retrieval_queries[0] == "what is the original question"


# --- ModelAssistedQueryTransformer: failure modes (Part 8) ---

def test_model_assisted_transformer_raises_on_missing_json() -> None:
    generator = FakeGenerator(response="not json at all")
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    with pytest.raises(QueryTransformerMalformedOutputError):
        transformer.transform(query="q")


def test_model_assisted_transformer_raises_on_missing_required_field() -> None:
    generator = FakeGenerator(response='{"alternate_query": null, "extracted_terms": []}')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    with pytest.raises(QueryTransformerMalformedOutputError):
        transformer.transform(query="q")


def test_model_assisted_transformer_raises_on_oversized_rewrite() -> None:
    oversized = "x" * 500
    generator = FakeGenerator(response=f'{{"rewritten_query": "{oversized}", "alternate_query": null, "extracted_terms": []}}')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model", max_query_chars=300)
    with pytest.raises(QueryTransformerMalformedOutputError):
        transformer.transform(query="q")


def test_model_assisted_transformer_handles_identical_rewrite() -> None:
    generator = FakeGenerator(response='{"rewritten_query": "same query", "alternate_query": null, "extracted_terms": []}')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    plan = transformer.transform(query="same query")
    assert plan.retrieval_queries == ("same query",)
    assert plan.status == "unchanged"


def test_model_assisted_transformer_handles_empty_rewrite() -> None:
    generator = FakeGenerator(response='{"rewritten_query": "", "alternate_query": null, "extracted_terms": []}')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    plan = transformer.transform(query="q")
    assert plan.retrieval_queries == ("q",)
    assert plan.status == "empty_rewrite"


def test_model_assisted_transformer_handles_empty_query() -> None:
    generator = FakeGenerator(response='{"rewritten_query": "irrelevant", "alternate_query": null, "extracted_terms": []}')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    plan = transformer.transform(query="   ")
    assert plan.status == "empty_rewrite"
    assert generator.calls == []  # never called the generator for an empty query


def test_model_assisted_transformer_raises_timeout_error_on_slow_generator() -> None:
    generator = FakeGenerator(response="{}", sleep_seconds=0.3)
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model", timeout_seconds=0.05)
    with pytest.raises(QueryTransformerTimeoutError):
        transformer.transform(query="q")


def test_model_assisted_transformer_wraps_generator_error() -> None:
    generator = FakeGenerator(raise_error=RuntimeError("provider exploded"))
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    with pytest.raises(QueryTransformerError):
        transformer.transform(query="q")


# --- build_query_transformer factory ---

def test_build_query_transformer_identity() -> None:
    transformer = build_query_transformer(provider_name=IDENTITY_PROVIDER)
    assert isinstance(transformer, IdentityQueryTransformer)


def test_build_query_transformer_deterministic() -> None:
    transformer = build_query_transformer(provider_name=DETERMINISTIC_PROVIDER)
    assert isinstance(transformer, DeterministicQueryTransformer)


def test_build_query_transformer_model_assisted_requires_generate_fn() -> None:
    with pytest.raises(QueryTransformerError):
        build_query_transformer(provider_name=MODEL_ASSISTED_PROVIDER, model_name="some-model")


def test_build_query_transformer_model_assisted_requires_model_name() -> None:
    with pytest.raises(QueryTransformerError):
        build_query_transformer(provider_name=MODEL_ASSISTED_PROVIDER, generate_fn=FakeGenerator(response="{}"))


def test_build_query_transformer_rejects_unsupported_provider() -> None:
    with pytest.raises(QueryTransformerError):
        build_query_transformer(provider_name="not_a_real_provider")


def test_build_query_transformer_applies_configurable_max_queries_deterministic() -> None:
    # settings.QUERY_TRANSFORMER_MAX_QUERIES (Part 7 hard cap) must actually
    # reach DeterministicQueryTransformer, not just exist as a declared
    # setting - a query that would otherwise produce 3 candidates is capped
    # to 2 (original + at most 1 more) when max_queries=2.
    transformer = build_query_transformer(provider_name=DETERMINISTIC_PROVIDER, max_queries=2)
    plan = transformer.transform(query="can you tell me the api sla config")
    assert len(plan.retrieval_queries) <= 2


def test_build_query_transformer_applies_configurable_max_queries_model_assisted() -> None:
    generator = FakeGenerator(response='{"rewritten_query": "rewrite one", "alternate_query": "rewrite two", "extracted_terms": []}')
    transformer = build_query_transformer(provider_name=MODEL_ASSISTED_PROVIDER, model_name="fake-model", generate_fn=generator, max_queries=2)
    plan = transformer.transform(query="original")
    assert len(plan.retrieval_queries) == 2
    assert plan.retrieval_queries == ("original", "rewrite one")


def test_build_query_transformer_clamps_non_positive_max_queries() -> None:
    transformer = build_query_transformer(provider_name=DETERMINISTIC_PROVIDER, max_queries=0)
    plan = transformer.transform(query="what is the sla")
    assert len(plan.retrieval_queries) >= 1


# --- transform_query: fail-safe (production) vs fail-loud (evaluation) ---

def test_transform_query_falls_back_to_original_query_on_failure_by_default() -> None:
    generator = FakeGenerator(raise_error=RuntimeError("boom"))
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    plan = transform_query(transformer, query="what is the refund window", fail_loud=False)
    assert plan.status == "failed"
    assert plan.error_message is not None
    assert plan.retrieval_queries == ("what is the refund window",)


def test_transform_query_fails_loud_for_evaluation() -> None:
    generator = FakeGenerator(raise_error=RuntimeError("boom"))
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    with pytest.raises(QueryTransformerError):
        transform_query(transformer, query="q", fail_loud=True)


def test_transform_query_identity_rollback_reproduces_original_only() -> None:
    plan = transform_query(IdentityQueryTransformer(), query="what is the refund window", fail_loud=False)
    assert plan.retrieval_queries == ("what is the refund window",)
    assert plan.status == "identity"


def test_transform_query_success_path_reports_ok_metadata() -> None:
    generator = FakeGenerator(response='{"rewritten_query": "rewritten", "alternate_query": null, "extracted_terms": []}')
    transformer = ModelAssistedQueryTransformer(generate=generator, model_name="fake-model")
    plan = transform_query(transformer, query="original", fail_loud=False)
    assert plan.status == "ok"
    assert plan.provider == MODEL_ASSISTED_PROVIDER
    assert plan.model == "fake-model"
    assert plan.latency_ms >= 0


# --- merge_multi_query_candidates: deterministic merge (Part 6) ---

def test_merge_keeps_max_dense_score_across_queries() -> None:
    per_query_matches = [
        [_match("a", score=0.4), _match("b", score=0.9)],
        [_match("a", score=0.8)],
    ]
    result = merge_multi_query_candidates(per_query_matches=per_query_matches, top_k=10)
    by_id = {c.match.chunk_id: c for c in result.candidates}
    assert by_id["a"].best_score == pytest.approx(0.8)
    assert by_id["a"].match.score == pytest.approx(0.8)  # dense score never overwritten with an incomparable value


def test_merge_tracks_matched_query_indices_and_appearances() -> None:
    per_query_matches = [
        [_match("a", score=0.5)],
        [_match("a", score=0.6), _match("b", score=0.3)],
    ]
    result = merge_multi_query_candidates(per_query_matches=per_query_matches, top_k=10)
    by_id = {c.match.chunk_id: c for c in result.candidates}
    assert by_id["a"].matched_query_indices == (0, 1)
    assert by_id["a"].appearances == 2
    assert by_id["b"].matched_query_indices == (1,)
    assert by_id["b"].appearances == 1


def test_merge_never_blindly_concatenates_never_duplicates_a_chunk() -> None:
    per_query_matches = [
        [_match("a", score=0.9), _match("b", score=0.5)],
        [_match("a", score=0.9), _match("b", score=0.5)],
    ]
    result = merge_multi_query_candidates(per_query_matches=per_query_matches, top_k=10)
    assert len(result.candidates) == 2
    assert result.total_raw_candidate_count == 4
    assert result.deduplicated_candidate_count == 2


def test_merge_orders_by_score_then_appearances_deterministically() -> None:
    per_query_matches = [
        [_match("a", score=0.5), _match("b", score=0.5)],
        [_match("b", score=0.5)],
    ]
    result = merge_multi_query_candidates(per_query_matches=per_query_matches, top_k=10)
    # "b" appears twice at the same score as "a" (once) - appearances break the tie.
    assert [c.match.chunk_id for c in result.candidates] == ["b", "a"]


def test_merge_respects_top_k() -> None:
    per_query_matches = [[_match(str(i), score=1.0 - i * 0.01) for i in range(5)]]
    result = merge_multi_query_candidates(per_query_matches=per_query_matches, top_k=2)
    assert len(result.candidates) == 2


def test_merge_is_deterministic_across_repeated_calls() -> None:
    per_query_matches = [
        [_match("a", score=0.5), _match("c", score=0.5)],
        [_match("b", score=0.5)],
    ]
    first = merge_multi_query_candidates(per_query_matches=per_query_matches, top_k=10)
    second = merge_multi_query_candidates(per_query_matches=per_query_matches, top_k=10)
    assert [c.match.chunk_id for c in first.candidates] == [c.match.chunk_id for c in second.candidates]


def test_merge_empty_input_produces_empty_result() -> None:
    result = merge_multi_query_candidates(per_query_matches=[[], []], top_k=10)
    assert result.candidates == []
    assert result.total_raw_candidate_count == 0
    assert result.deduplicated_candidate_count == 0


def test_merge_never_introduces_documents_outside_the_input_candidate_set() -> None:
    per_query_matches = [
        [_match("a", document_id="doc-1", score=0.5)],
        [_match("b", document_id="doc-2", score=0.4)],
    ]
    result = merge_multi_query_candidates(per_query_matches=per_query_matches, top_k=10)
    allowed_document_ids = {"doc-1", "doc-2"}
    assert all(c.match.document_id in allowed_document_ids for c in result.candidates)
