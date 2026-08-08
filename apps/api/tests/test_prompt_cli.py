from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, EvaluationCase, EvaluationDataset, Organisation, User, Workspace
from app.db.models.prompt import LAYER_ASSISTANT_PERSONA_TONE
from app.evaluation.categories import Answerability, CaseCategory
from app.operations import prompt_promote
from app.repositories import prompt_repository as repo


@pytest.fixture()
def seeded_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Uses a pathlib.Path-based sqlite file (Windows/Linux-agnostic - see
    docs/06_Operations for the CLI's OS-independence requirement). Two
    separate things need to target this same file: the CLI's own
    `SessionLocal` (monkeypatched directly, following
    tests/test_eval_release_gate_check.py's precedent - app.db.session.engine
    is a module-level singleton bound at import time, so overriding
    settings.DATABASE_URL alone would not affect it) and
    app.evaluation.shadow_session's per-case shadow session, which reads
    settings.DATABASE_URL fresh on every call (not import-time-frozen), so
    that override alone is sufficient for it."""
    db_path = tmp_path / "prompt-cli-test.db"
    db_url = f"sqlite:///{db_path}"

    original_provider = settings.EMBEDDING_PROVIDER
    original_model = settings.EMBEDDING_MODEL
    original_dimension = settings.EMBEDDING_DIMENSION
    original_database_url = settings.DATABASE_URL
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "prompt-cli-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    object.__setattr__(settings, "DATABASE_URL", db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(prompt_promote, "SessionLocal", sessionmaker(bind=engine))
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    unique = uuid4().hex[:8]
    org = Organisation(name="CLI Org", slug=f"cli-org-{unique}", status="active")
    workspace = Workspace(organisation=org, name="Workspace", slug=f"cli-workspace-{unique}", status="active")
    user = User(email=f"owner-{unique}@example.test")
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
        embedding_provider="local-mock", embedding_model="prompt-cli-test", embedding_dimension=8,
        embedding_created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    widget = create_widget(db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user.id, initial_configuration={"knowledge_scope_json": [document.id]})

    dataset = EvaluationDataset(organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, name="CLI dataset", version="1", status="active")
    db.add(dataset)
    db.flush()
    db.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=org.id, workspace_id=workspace.id,
        question="When do applications close?", expected_document_ids=[document.id],
        expected_answerability=Answerability.ANSWERABLE.value, category=CaseCategory.ANSWERABLE_FACTUAL.value,
    ))
    db.commit()
    db.refresh(dataset)

    repo.get_or_create_platform_core_template(db)
    persona_template = repo.get_or_create_workspace_template(db, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona")
    candidate = repo.create_draft_version(db, template=persona_template, content="Be friendly.", variables_schema=[], author_user_id=user.id)

    yield {"organisation_id": org.id, "workspace_id": workspace.id, "widget_id": widget.id, "dataset_id": dataset.id, "candidate_version_id": candidate.id}

    db.close()
    engine.dispose()
    object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
    object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
    object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)
    object.__setattr__(settings, "DATABASE_URL", original_database_url)


def test_cli_exits_zero_on_passing_gate(seeded_db: dict) -> None:
    exit_code = prompt_promote.main([
        "--candidate-version", seeded_db["candidate_version_id"],
        "--dataset", seeded_db["dataset_id"],
        "--assistant", seeded_db["widget_id"],
        "--organisation", seeded_db["organisation_id"],
        "--workspace", seeded_db["workspace_id"],
        "--format", "json",
    ])
    assert exit_code == 0


def test_cli_exits_two_on_missing_dataset(seeded_db: dict) -> None:
    exit_code = prompt_promote.main([
        "--candidate-version", seeded_db["candidate_version_id"],
        "--dataset", "does-not-exist",
        "--assistant", seeded_db["widget_id"],
        "--organisation", seeded_db["organisation_id"],
        "--workspace", seeded_db["workspace_id"],
    ])
    assert exit_code == 2


def test_cli_text_format_output(seeded_db: dict, capsys: pytest.CaptureFixture) -> None:
    exit_code = prompt_promote.main([
        "--candidate-version", seeded_db["candidate_version_id"],
        "--dataset", seeded_db["dataset_id"],
        "--assistant", seeded_db["widget_id"],
        "--organisation", seeded_db["organisation_id"],
        "--workspace", seeded_db["workspace_id"],
    ])
    captured = capsys.readouterr()
    assert "Prompt promotion gate for candidate" in captured.out
    assert exit_code in (0, 1)
