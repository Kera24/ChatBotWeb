from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.ai.dependencies import create_ai_core
from app.ai.rag_orchestrator import RAGOrchestrationRequest, RAGOrchestrator, RAGOrchestratorDependencies
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Organisation, User, Workspace
from app.db.models.ai_trace import AIModelCallTrace, AITraceStage
from app.db.models.prompt import LAYER_ASSISTANT_PERSONA_TONE, LAYER_PLATFORM_CORE
from app.observability.ai_trace_recorder import SqlAlchemyAITraceRecorder
from app.repositories import prompt_repository as repo
from app.services.embeddings import build_embedding_provider


@pytest.fixture()
def db_session():
    original_provider = settings.EMBEDDING_PROVIDER
    original_model = settings.EMBEDDING_MODEL
    original_dimension = settings.EMBEDDING_DIMENSION
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "prompt-trace-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)

    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    session.session_factory = session_factory  # stashed for tests that need a fresh session to see the trace recorder's separately-committed rows
    yield session
    session.close()
    engine.dispose()

    object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
    object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
    object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)


def _seed_tenant_with_document(db: Session, *, suffix: str):
    unique = uuid4().hex[:8]
    org = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}-{unique}", status="active")
    workspace = Workspace(organisation=org, name="Workspace", slug=f"workspace-{suffix}-{unique}", status="active")
    user = User(email=f"owner-{suffix}-{unique}@example.test")
    db.add_all([org, workspace, user])
    db.commit()

    document = Document(organisation_id=org.id, workspace_id=workspace.id, title="FAQ", source_type="txt", source_key="faq.txt", status="ready")
    db.add(document)
    db.flush()
    version = DocumentVersion(organisation_id=org.id, workspace_id=workspace.id, document_id=document.id, version_number=1, checksum="c1", processing_status="ready")
    db.add(version)
    db.flush()
    document.active_document_version_id = version.id
    db.add(Chunk(
        organisation_id=org.id, workspace_id=workspace.id, document_id=document.id, document_version_id=version.id,
        chunk_index=0, content="Applications close on March 1st.", content_hash="h1", token_count=5,
        source_type="txt", source_title="FAQ", status="ready",
        embedding_provider="local-mock", embedding_model="prompt-trace-test", embedding_dimension=8,
        embedding_created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    widget = create_widget(db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user.id, initial_configuration={"knowledge_scope_json": [document.id]})
    return org, workspace, widget, user.id


def _orchestrator(db: Session) -> RAGOrchestrator:
    recorder = SqlAlchemyAITraceRecorder(session_factory=sessionmaker(bind=db.get_bind()))
    return RAGOrchestrator(
        RAGOrchestratorDependencies(
            db=db, ai_core=create_ai_core(), embedding_provider=build_embedding_provider(provider_name="local-mock", model_name="prompt-trace-test", dimension=8),
            trace_recorder=recorder,
        )
    )


def test_dormant_prompt_management_leaves_trace_prompt_fields_as_before(db_session: Session) -> None:
    org, workspace, widget, _user_id = _seed_tenant_with_document(db_session, suffix="dormant")
    orchestrator = _orchestrator(db_session)

    result = orchestrator.answer(RAGOrchestrationRequest(organisation_id=org.id, workspace_id=workspace.id, assistant_id=widget.id, query="When do applications close?"))
    assert result.answer_state == "answered"

    with db_session.session_factory() as verify_db:
        model_call = verify_db.execute(select(AIModelCallTrace).where(AIModelCallTrace.trace_id == _trace_id_for(verify_db, result.trace_id))).scalar_one()
        assert model_call.prompt_key == "grounded_rag_answer"
        assert model_call.prompt_version_id is None
        assert model_call.experiment_id is None
        assert model_call.resolved_layer_version_ids is None


def test_composite_prompt_identity_lands_on_model_call_trace(db_session: Session) -> None:
    org, workspace, widget, user_id = _seed_tenant_with_document(db_session, suffix="composite")
    platform_template = repo.get_or_create_platform_core_template(db_session)
    persona_template = repo.get_or_create_workspace_template(db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona")
    draft = repo.create_draft_version(db_session, template=persona_template, content="Sign every answer with -Acme Bot.", variables_schema=[], author_user_id=user_id)
    under_eval = repo.transition_version_status(db_session, version=draft, new_status="under_evaluation", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
    approved = repo.transition_version_status(db_session, version=under_eval, new_status="approved", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
    repo.deploy_version(db_session, version=approved, template=persona_template, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, actor_user_id=user_id)

    orchestrator = _orchestrator(db_session)
    result = orchestrator.answer(RAGOrchestrationRequest(organisation_id=org.id, workspace_id=workspace.id, assistant_id=widget.id, query="When do applications close?"))
    assert result.answer_state == "answered"

    platform_version_id = repo.list_versions(db_session, template_id=platform_template.id)[0].id
    with db_session.session_factory() as verify_db:
        trace_row_id = _trace_id_for(verify_db, result.trace_id)
        model_call = verify_db.execute(select(AIModelCallTrace).where(AIModelCallTrace.trace_id == trace_row_id)).scalar_one()
        assert model_call.prompt_version_id == platform_version_id
        assert model_call.resolved_layer_version_ids[LAYER_PLATFORM_CORE] == platform_version_id
        assert model_call.resolved_layer_version_ids[LAYER_ASSISTANT_PERSONA_TONE] == approved.id
        assert model_call.prompt_version.startswith("core:v1+persona:v1")

        stage = verify_db.execute(
            select(AITraceStage).where(AITraceStage.trace_id == trace_row_id, AITraceStage.stage_name == "prompt_construction")
        ).scalar_one()
        assert stage.status == "ok"


def _trace_id_for(db: Session, trace_id: str) -> str:
    from app.db.models.ai_trace import AITrace

    return db.execute(select(AITrace.id).where(AITrace.trace_id == trace_id)).scalar_one()
