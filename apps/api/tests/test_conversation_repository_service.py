from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Organisation, Workspace
from app.repositories.conversation_repository import (
    CitationValidationError,
    ConversationNotFound,
    create_message,
    get_conversation,
    get_message,
    list_citations_for_message,
    list_conversations,
    list_messages,
)
from app.repositories.document_repository import (
    create_chunk_for_workspace,
    create_document_for_workspace,
    create_document_version_for_workspace,
)
from app.services.conversation import (
    InvalidConversationStatusTransition,
    append_assistant_message,
    append_user_message,
    archive_conversation,
    attach_citations_to_assistant_message,
    mark_conversation_completed,
    start_conversation,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as session:
        yield session

    Base.metadata.drop_all(engine)


def seed_tenants(db_session: Session) -> tuple[Organisation, Organisation, Workspace, Workspace]:
    org_a = Organisation(name="Alpha College", slug="alpha")
    org_b = Organisation(name="Beta Clinic", slug="beta")
    workspace_a = Workspace(organisation=org_a, name="Admissions", slug="admissions")
    workspace_b = Workspace(organisation=org_b, name="Patient Help", slug="patient-help")
    db_session.add_all([org_a, org_b, workspace_a, workspace_b])
    db_session.commit()
    return org_a, org_b, workspace_a, workspace_b


def seed_ready_chunk(db_session: Session, *, organisation_id: str, workspace_id: str):
    document = create_document_for_workspace(
        db_session,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        title="Admissions Handbook",
        source_type="pdf",
        source_key=f"{organisation_id}-{workspace_id}.pdf",
    )
    version = create_document_version_for_workspace(
        db_session,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document.id,
        version_number=1,
        checksum=f"sha256:{document.id}",
    )
    chunk = create_chunk_for_workspace(
        db_session,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document.id,
        document_version_id=version.id,
        chunk_index=0,
        content="Applications close in December.",
        content_hash=f"sha256:{version.id}",
        source_type="pdf",
        source_title="Admissions Handbook",
        status="ready",
    )
    return document, version, chunk


def test_conversation_creation_and_tenant_safe_lookup(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b = seed_tenants(db_session)

    conversation = start_conversation(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        channel="dashboard_test",
        title="Test chat",
    )

    assert conversation.id is not None
    assert conversation.status == "active"
    assert get_conversation(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, conversation_id=conversation.id)
    assert get_conversation(db_session, organisation_id=org_b.id, workspace_id=workspace_b.id, conversation_id=conversation.id) is None


def test_workspace_scoped_conversation_listing_and_cross_tenant_isolation(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b = seed_tenants(db_session)
    conversation_a = start_conversation(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, channel="widget")
    conversation_b = start_conversation(db_session, organisation_id=org_b.id, workspace_id=workspace_b.id, channel="widget")

    org_a_conversations = list_conversations(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id)
    org_b_conversations = list_conversations(db_session, organisation_id=org_b.id, workspace_id=workspace_b.id)

    assert [item.id for item in org_a_conversations] == [conversation_a.id]
    assert [item.id for item in org_b_conversations] == [conversation_b.id]


def test_user_and_assistant_messages_sequence_metadata_and_order(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    conversation = start_conversation(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, channel="api")

    user_message = append_user_message(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
        content="When do applications close?",
    )
    assistant_message = append_assistant_message(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
        content="Applications close in December.",
        answer_state="answered",
        model_key="mock-default",
        provider_key="mock",
        provider_model_name="mock-model-v1",
        prompt_key="grounded_rag_answer",
        prompt_version=3,
        prompt_hash="sha256:prompt",
        execution_id="exec-123",
        input_tokens=10,
        output_tokens=6,
        total_tokens=16,
        estimated_cost=Decimal("0.00001234"),
        latency_ms=42,
        finish_reason="stop",
        metadata_json={"attempts": 1},
    )

    messages = list_messages(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, conversation_id=conversation.id)
    db_session.refresh(conversation)

    assert user_message.sequence_number == 1
    assert assistant_message.sequence_number == 2
    assert [message.id for message in messages] == [user_message.id, assistant_message.id]
    assert conversation.last_message_at == assistant_message.created_at
    assert assistant_message.execution_id == "exec-123"
    assert assistant_message.metadata_json == {"attempts": 1}
    assert assistant_message.estimated_cost == Decimal("0.00001234")


def test_duplicate_sequence_rejected(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    conversation = start_conversation(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, channel="api")
    first = append_user_message(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
        content="Hello",
    )

    with pytest.raises(IntegrityError):
        create_message(
            db_session,
            organisation_id=org_a.id,
            workspace_id=workspace_a.id,
            conversation_id=conversation.id,
            role="user",
            content="Duplicate",
            sequence_number=first.sequence_number,
            created_at=first.created_at,
        )


def test_cross_tenant_message_access_denied(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b = seed_tenants(db_session)
    conversation = start_conversation(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, channel="api")
    message = append_user_message(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
        content="Hello",
    )

    assert get_message(
        db_session,
        organisation_id=org_b.id,
        workspace_id=workspace_b.id,
        conversation_id=conversation.id,
        message_id=message.id,
    ) is None
    with pytest.raises(ConversationNotFound):
        append_user_message(
            db_session,
            organisation_id=org_b.id,
            workspace_id=workspace_b.id,
            conversation_id=conversation.id,
            content="Cross tenant",
        )


def test_citation_creation_validation_and_listing(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    _document, _version, chunk = seed_ready_chunk(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id)
    conversation = start_conversation(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, channel="dashboard_test")
    assistant_message = append_assistant_message(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
        content="Applications close in December.",
    )

    created = attach_citations_to_assistant_message(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        citations=[
            {
                "chunk_id": chunk.id,
                "citation_index": 1,
                "similarity_score": Decimal("0.912345"),
                "quoted_text": "Applications close in December.",
            }
        ],
    )
    listed = list_citations_for_message(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
        message_id=assistant_message.id,
    )

    assert [citation.id for citation in listed] == [created[0].id]
    assert listed[0].chunk_id == chunk.id
    assert listed[0].source_title == "Admissions Handbook"


def test_citation_rejects_wrong_tenant_chunk_and_non_assistant_message(db_session: Session) -> None:
    org_a, org_b, workspace_a, workspace_b = seed_tenants(db_session)
    _document_b, _version_b, chunk_b = seed_ready_chunk(db_session, organisation_id=org_b.id, workspace_id=workspace_b.id)
    conversation = start_conversation(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, channel="dashboard_test")
    user_message = append_user_message(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
        content="Hello",
    )
    assistant_message = append_assistant_message(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
        content="Hello.",
    )

    with pytest.raises(CitationValidationError):
        attach_citations_to_assistant_message(
            db_session,
            organisation_id=org_a.id,
            workspace_id=workspace_a.id,
            conversation_id=conversation.id,
            message_id=user_message.id,
            citations=[{"chunk_id": chunk_b.id, "citation_index": 1}],
        )
    with pytest.raises(CitationValidationError):
        attach_citations_to_assistant_message(
            db_session,
            organisation_id=org_a.id,
            workspace_id=workspace_a.id,
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            citations=[{"chunk_id": chunk_b.id, "citation_index": 1}],
        )


def test_conversation_status_transitions(db_session: Session) -> None:
    org_a, _org_b, workspace_a, _workspace_b = seed_tenants(db_session)
    conversation = start_conversation(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, channel="widget")

    completed = mark_conversation_completed(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
    )
    assert completed.status == "completed"
    assert completed.ended_at is not None

    archived = archive_conversation(
        db_session,
        organisation_id=org_a.id,
        workspace_id=workspace_a.id,
        conversation_id=conversation.id,
    )

    assert archived.status == "archived"
    with pytest.raises(InvalidConversationStatusTransition):
        mark_conversation_completed(
            db_session,
            organisation_id=org_a.id,
            workspace_id=workspace_a.id,
            conversation_id=conversation.id,
        )


def test_alembic_migration_upgrade_passes(tmp_path: Path) -> None:
    database_path = tmp_path / "conversation-migration.sqlite"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")
