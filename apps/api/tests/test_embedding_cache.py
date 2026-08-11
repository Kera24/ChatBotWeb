"""Tests for app.evaluation.embedding_cache.CachingEmbeddingProvider - the
Retrieval V2 Phase 1 follow-up fix for real-embedding bake-off performance
(SQLite's no-index retrieval path re-embeds every candidate chunk on every
query; this cache memoises embed() so each unique chunk is only ever
embedded once per run)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, EvaluationCase, EvaluationDataset, Membership, Organisation, User, Workspace
from app.evaluation.categories import Answerability, CaseCategory
from app.evaluation.embedding_cache import CachingEmbeddingProvider
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.repositories.evaluation_repository import list_results_for_run
from app.services.embeddings import LocalMockEmbeddingProvider
from app.services.vector_search import search_embedded_chunks


class _CountingProvider:
    def __init__(self, *, dimension: int = 4, model_name: str = "counting-v1", provider_name: str = "counting") -> None:
        self.dimension = dimension
        self.model_name = model_name
        self.provider_name = provider_name
        self.call_count = 0
        self._inner = LocalMockEmbeddingProvider(dimension=dimension, model_name=model_name)

    def embed(self, text: str) -> list[float]:
        self.call_count += 1
        return self._inner.embed(text)


# --- unit tests on CachingEmbeddingProvider directly ------------------------


def test_same_text_embeds_once() -> None:
    inner = _CountingProvider()
    cache = CachingEmbeddingProvider(inner=inner)

    first = cache.embed("the same chunk content")
    second = cache.embed("the same chunk content")
    third = cache.embed("the same chunk content")

    assert inner.call_count == 1
    assert first == second == third
    assert cache.hit_count == 2
    assert cache.miss_count == 1


def test_changed_content_reembeds() -> None:
    inner = _CountingProvider()
    cache = CachingEmbeddingProvider(inner=inner)

    cache.embed("chunk A")
    cache.embed("chunk B")
    cache.embed("chunk A")  # hit

    assert inner.call_count == 2
    assert cache.hit_count == 1
    assert cache.miss_count == 2


def test_different_model_does_not_collide() -> None:
    """Swapping .inner mid-life (simulating a wrapper reused across a model
    switch) must never return a stale vector embedded under a different
    model - the cache key includes model_name, not just text."""
    cache = CachingEmbeddingProvider(inner=_CountingProvider(model_name="model-a", dimension=4))
    vector_a = cache.embed("shared text")
    assert cache.miss_count == 1

    cache.inner = _CountingProvider(model_name="model-b", dimension=4)
    vector_b = cache.embed("shared text")

    assert cache.miss_count == 2  # not a cache hit, despite identical text
    assert cache.hit_count == 0


def test_different_dimension_does_not_collide() -> None:
    cache = CachingEmbeddingProvider(inner=_CountingProvider(dimension=4))
    vector_small = cache.embed("shared text")
    assert len(vector_small) == 4

    cache.inner = _CountingProvider(dimension=8)
    vector_large = cache.embed("shared text")

    assert len(vector_large) == 8
    assert cache.miss_count == 2
    assert cache.hit_count == 0


def test_stats_reports_hit_and_miss_counts() -> None:
    cache = CachingEmbeddingProvider(inner=_CountingProvider())
    cache.embed("x")
    cache.embed("x")
    cache.embed("y")

    assert cache.stats() == {"embedding_cache_hit_count": 1, "embedding_cache_miss_count": 2}


def test_provider_identity_passes_through_unchanged() -> None:
    inner = _CountingProvider(provider_name="ollama", model_name="nomic-embed-text-v2-moe", dimension=768)
    cache = CachingEmbeddingProvider(inner=inner)
    assert cache.provider_name == "ollama"
    assert cache.model_name == "nomic-embed-text-v2-moe"
    assert cache.dimension == 768


# --- cache must not change retrieval results --------------------------------


def test_cache_does_not_change_search_embedded_chunks_results() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    try:
        organisation = Organisation(name="Cache Org", slug="cache-org", status="active", plan_key="starter")
        workspace = Workspace(organisation=organisation, name="Workspace", slug="cache-workspace", status="active", default_language="en")
        user = User(email="owner-cache@example.test", full_name="Owner")
        membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
        db.add_all([organisation, workspace, user, membership])
        db.commit()

        provider = LocalMockEmbeddingProvider(dimension=8, model_name="cache-equivalence-test")
        for key, content in [("a", "applications close in december"), ("b", "refunds take seven business days"), ("c", "the pipeline supports twenty five matrix combinations")]:
            document = Document(organisation_id=organisation.id, workspace_id=workspace.id, title=key, source_type="txt", source_key=f"{key}.txt", status="ready")
            db.add(document)
            db.flush()
            version = DocumentVersion(organisation_id=organisation.id, workspace_id=workspace.id, document_id=document.id, version_number=1, checksum=f"checksum-{key}", processing_status="ready")
            db.add(version)
            db.flush()
            document.active_document_version_id = version.id
            chunk = Chunk(
                organisation_id=organisation.id, workspace_id=workspace.id, document_id=document.id, document_version_id=version.id,
                chunk_index=0, content=content, content_hash=f"hash-{key}", token_count=len(content.split()),
                source_type="txt", source_title=key, status="ready",
                embedding_provider=provider.provider_name, embedding_model=provider.model_name, embedding_dimension=provider.dimension,
                embedding_created_at=datetime.now(timezone.utc),
            )
            db.add(chunk)
        db.commit()

        uncached = search_embedded_chunks(db, organisation_id=organisation.id, workspace_id=workspace.id, query="applications close in december", limit=10, provider=provider)
        cached_provider = CachingEmbeddingProvider(inner=provider)
        cached = search_embedded_chunks(db, organisation_id=organisation.id, workspace_id=workspace.id, query="applications close in december", limit=10, provider=cached_provider)

        assert [(m.chunk_id, m.score) for m in uncached] == [(m.chunk_id, m.score) for m in cached]
        # A second identical query against the same (already-warm) cached
        # provider must still return byte-identical results.
        cached_again = search_embedded_chunks(db, organisation_id=organisation.id, workspace_id=workspace.id, query="applications close in december", limit=10, provider=cached_provider)
        assert [(m.chunk_id, m.score) for m in cached] == [(m.chunk_id, m.score) for m in cached_again]
        assert cached_provider.hit_count > 0
    finally:
        db.close()
        engine.dispose()


# --- run_evaluation integration ---------------------------------------------


@pytest.fixture()
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'eval-embedding-cache.db'}"


@pytest.fixture()
def db_session(db_url: str):
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "cache-engine-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _seed_document(db: Session, *, organisation_id: str, workspace_id: str, key: str, title: str, content: str) -> str:
    document = Document(organisation_id=organisation_id, workspace_id=workspace_id, title=title, source_type="txt", source_key=f"{key}.txt", status="ready")
    db.add(document)
    db.flush()
    version = DocumentVersion(organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, version_number=1, checksum=f"checksum-{key}", processing_status="ready")
    db.add(version)
    db.flush()
    document.active_document_version_id = version.id
    chunk = Chunk(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, document_version_id=version.id,
        chunk_index=0, content=content, content_hash=f"hash-{key}", token_count=len(content.split()),
        source_type="txt", source_title=title, status="ready",
        embedding_provider="local-mock", embedding_model="cache-engine-test", embedding_dimension=8,
        embedding_created_at=datetime.now(timezone.utc),
    )
    db.add(chunk)
    db.commit()
    return document.id


def _seed_tenant(db: Session, *, suffix: str) -> tuple[Organisation, Workspace, str]:
    organisation = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug=f"workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"owner-{suffix}@example.test", full_name="Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    return organisation, workspace, user.id


def _make_dataset_with_two_cases(db: Session, *, organisation: Organisation, workspace: Workspace, widget_id: str, document_id: str) -> EvaluationDataset:
    """Two different questions that both retrieve the SAME chunk - proves
    the chunk is embedded once across cases, not once per case."""
    dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget_id, name="Cache engine test dataset", version="1", status="active")
    db.add(dataset)
    db.flush()
    db.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="When do applications close?", expected_document_ids=[document_id],
        expected_answerability=Answerability.ANSWERABLE.value, category=CaseCategory.ANSWERABLE_FACTUAL.value,
    ))
    db.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
        question="Tell me when applications close please", expected_document_ids=[document_id],
        expected_answerability=Answerability.ANSWERABLE.value, category=CaseCategory.ANSWERABLE_FACTUAL.value,
    ))
    db.commit()
    db.refresh(dataset)
    return dataset


def test_run_evaluation_records_cache_hit_and_miss_counts(db_session: Session, db_url: str) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="cache-hits")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = _make_dataset_with_two_cases(db_session, organisation=organisation, workspace=workspace, widget_id=widget.id, document_id=document_id)

    run = run_evaluation(
        db_session, dataset=dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id,
        options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url, embedding_cache_enabled=True),
    )

    assert run.status == "completed"
    assert run.total_cases == 2
    # The single seeded chunk is a retrieval candidate for both cases - with
    # caching enabled its content is only ever embedded once, so the second
    # case's retrieval call must register at least one cache hit.
    assert run.retrieval_settings_json["embedding_cache_hit_count"] >= 1


def test_run_evaluation_cache_enabled_vs_disabled_identical_results(db_session: Session, db_url: str) -> None:
    organisation, workspace, user_id = _seed_tenant(db_session, suffix="cache-equiv")
    document_id = _seed_document(db_session, organisation_id=organisation.id, workspace_id=workspace.id, key="faq", title="FAQ", content="Applications close on March 1st.")
    widget = create_widget(db_session, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user_id, initial_configuration={"knowledge_scope_json": [document_id]})
    dataset = _make_dataset_with_two_cases(db_session, organisation=organisation, workspace=workspace, widget_id=widget.id, document_id=document_id)

    run_cached = run_evaluation(
        db_session, dataset=dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id,
        options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url, embedding_cache_enabled=True),
    )
    run_uncached = run_evaluation(
        db_session, dataset=dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id,
        options=EvaluationRunOptions(mode="mock", shadow_database_url=db_url, embedding_cache_enabled=False),
    )

    cached_results = sorted(list_results_for_run(db_session, run_id=run_cached.id), key=lambda r: r.case_id)
    uncached_results = sorted(list_results_for_run(db_session, run_id=run_uncached.id), key=lambda r: r.case_id)

    assert [r.passed for r in cached_results] == [r.passed for r in uncached_results]
    assert [r.answer_state for r in cached_results] == [r.answer_state for r in uncached_results]
    assert [r.retrieved_chunk_ids for r in cached_results] == [r.retrieved_chunk_ids for r in uncached_results]
    assert [r.retrieval_metrics_json.get("recall_at_k") for r in cached_results] == [r.retrieval_metrics_json.get("recall_at_k") for r in uncached_results]
