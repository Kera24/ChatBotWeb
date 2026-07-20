from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.access.credentials.service import add_origin, create_credential, transition_credential
from app.access.observability.events import InMemoryAccessEventSink
from app.access.rate_limit.redis_store import InMemoryRateLimitStore
from app.access.widget_config.service import publish_configuration, upsert_draft_configuration
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Organisation, PublicCredential, User, Workspace
from app.db.session import get_db
from app.main import create_app

ALPHA_ORIGIN = "http://127.0.0.1:5101"
BETA_ORIGIN = "http://127.0.0.1:5102"
UNAUTHORISED_ORIGIN = "http://127.0.0.1:5199"

ALPHA_FACT = "The Alpha Observatory operates the Aurora chamber at Meridian Base."
BETA_FACT = "The Beta Archive maintains the Cobalt library at Harbor Station."
ALPHA_TITLE = "Alpha Observatory Synthetic Guide"
BETA_TITLE = "Beta Archive Synthetic Guide"
SYNTHETIC_MARKER = "synthetic-widget-b2"


@dataclass(frozen=True)
class SyntheticWidget:
    label: str
    public_key: str
    origin: str
    bot_name: str
    welcome_message: str
    fact: str
    source_title: str
    credential_id: str
    organisation_id: str
    workspace_id: str


def assert_safe_real_backend_environment(env: dict[str, str] | None = None, *, database_url: str = "sqlite+pysqlite:///:memory:") -> None:
    candidate = env or dict(os.environ)
    if candidate.get("WIDGET_REAL_BACKEND_TEST") != "1":
        raise RuntimeError("WIDGET_REAL_BACKEND_TEST=1 is required before synthetic real-backend fixtures are created.")

    app_env = (candidate.get("APP_ENV") or candidate.get("NODE_ENV") or "").lower()
    if app_env not in {"test", "testing", "synthetic-test"}:
        raise RuntimeError("APP_ENV or NODE_ENV must identify an explicit test environment.")

    lowered_url = database_url.lower()
    forbidden = ("production", "prod", "staging", "customer", "postgres://", "postgresql://")
    if any(value in lowered_url for value in forbidden):
        raise RuntimeError("Synthetic real-backend verification refuses production-like or external database URLs.")

    if not lowered_url.startswith("sqlite"):
        raise RuntimeError("The default synthetic real-backend suite only permits an isolated SQLite database.")


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("WIDGET_REAL_BACKEND_TEST", "1")
    monkeypatch.setenv("APP_ENV", "test")
    assert_safe_real_backend_environment(database_url="sqlite+pysqlite:///:memory:")

    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    app = create_app()
    app.state.testing_session = TestingSession
    app.state.public_widget_rate_limit_store = InMemoryRateLimitStore()
    app.state.public_widget_event_sink = InMemoryAccessEventSink()

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def seed_synthetic_widget(
    client: TestClient,
    *,
    label: str,
    origin: str,
    bot_name: str,
    welcome_message: str,
    primary_colour: str,
    fact: str,
    source_title: str,
    section_title: str,
    published: bool = True,
) -> SyntheticWidget:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name=f"{SYNTHETIC_MARKER}-{label}-org", slug=f"{SYNTHETIC_MARKER}-{label}-{unique}", status="active")
        user = User(email=f"{SYNTHETIC_MARKER}-{label}-{unique}@example.test")
        workspace = Workspace(organisation=org, name=f"{SYNTHETIC_MARKER}-{label}-workspace", slug=f"{SYNTHETIC_MARKER}-{label}-workspace-{unique}", status="active")
        db.add_all([org, user, workspace])
        db.commit()

        credential = create_credential(
            db,
            organisation_id=org.id,
            workspace_id=workspace.id,
            credential_type="widget_public_key",
            display_name=f"{SYNTHETIC_MARKER}-{label}-widget",
            environment="development",
            policy_profile="widget",
            capabilities=["widget_config"],
            created_by_user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        credential = transition_credential(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, target_status="active", actor_user_id=user.id)
        add_origin(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, origin=origin, wildcard_subdomains=False, actor_user_id=user.id)
        upsert_draft_configuration(
            db,
            organisation_id=org.id,
            workspace_id=workspace.id,
            credential_id=credential.id,
            actor_user_id=user.id,
            payload={
                "bot_name": bot_name,
                "welcome_message": welcome_message,
                "launcher_label": f"{label.title()} synthetic chat",
                "primary_colour": primary_colour,
                "secondary_colour": "#111827",
                "show_citations": True,
                "allow_conversation_history": True,
                "suggested_questions_json": [fact, f"What does {label.title()} know?"],
                "max_initial_suggestions": 2,
                "privacy_notice_text": "Synthetic verification data only.",
                "privacy_notice_url": "https://example.com/privacy",
                "terms_url": "https://example.com/terms",
                "fallback_contact_text": "Synthetic support is unavailable.",
            },
        )
        if published:
            publish_configuration(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, actor_user_id=user.id)

        _add_synthetic_chunk(
            db,
            credential=credential,
            content=fact,
            title=source_title,
            section_title=section_title,
        )
        db.commit()

        return SyntheticWidget(
            label=label,
            public_key=credential.public_identifier,
            origin=origin,
            bot_name=bot_name,
            welcome_message=welcome_message,
            fact=fact,
            source_title=source_title,
            credential_id=credential.id,
            organisation_id=org.id,
            workspace_id=workspace.id,
        )


def seed_alpha_beta(client: TestClient) -> tuple[SyntheticWidget, SyntheticWidget]:
    alpha = seed_synthetic_widget(
        client,
        label="alpha",
        origin=ALPHA_ORIGIN,
        bot_name="Alpha Synthetic Assistant",
        welcome_message="Alpha synthetic verification is ready.",
        primary_colour="#0f766e",
        fact=ALPHA_FACT,
        source_title=ALPHA_TITLE,
        section_title="Alpha synthetic section",
    )
    beta = seed_synthetic_widget(
        client,
        label="beta",
        origin=BETA_ORIGIN,
        bot_name="Beta Synthetic Assistant",
        welcome_message="Beta synthetic verification is ready.",
        primary_colour="#1d4ed8",
        fact=BETA_FACT,
        source_title=BETA_TITLE,
        section_title="Beta synthetic section",
    )
    return alpha, beta


def create_public_session(client: TestClient, widget: SyntheticWidget) -> str:
    response = client.post(
        f"/api/v1/widget/{widget.public_key}/sessions",
        headers={"Origin": widget.origin, "Content-Type": "application/json", "X-Request-ID": f"req-{widget.label}-session"},
        json={"client_request_id": f"{widget.label}-synthetic-session"},
    )
    assert response.status_code == 201, response.text
    return response.json()["session_token"]


def post_widget_message(
    client: TestClient,
    widget: SyntheticWidget,
    token: str,
    *,
    message: str,
    idempotency_key: str,
    origin: str | None = None,
):
    headers = {
        "Origin": origin or widget.origin,
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
        "X-Request-ID": f"req-{idempotency_key}",
    }
    return client.post(f"/api/v1/widget/{widget.public_key}/messages", headers=headers, json={"session_token": token, "message": message})


def _add_synthetic_chunk(
    db: Session,
    *,
    credential: PublicCredential,
    content: str,
    title: str,
    section_title: str,
) -> None:
    document = Document(
        organisation_id=credential.organisation_id,
        workspace_id=credential.workspace_id,
        title=title,
        source_type="txt",
        source_key=f"{SYNTHETIC_MARKER}-{title}.txt",
        status="ready",
    )
    db.add(document)
    db.flush()
    version = DocumentVersion(
        organisation_id=credential.organisation_id,
        workspace_id=credential.workspace_id,
        document_id=document.id,
        version_number=1,
        checksum=f"{SYNTHETIC_MARKER}-checksum-{title}",
        processing_status="ready",
    )
    db.add(version)
    db.flush()
    document.active_document_version_id = version.id
    db.add(
        Chunk(
            organisation_id=credential.organisation_id,
            workspace_id=credential.workspace_id,
            document_id=document.id,
            document_version_id=version.id,
            chunk_index=0,
            content=content,
            content_hash=f"{SYNTHETIC_MARKER}-hash-{title}",
            token_count=len(content.split()),
            source_type="txt",
            source_title=title,
            page_number=1,
            section_title=section_title,
            status="ready",
            embedding_provider="local-mock",
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            embedding_created_at=datetime.now(timezone.utc),
        )
    )

