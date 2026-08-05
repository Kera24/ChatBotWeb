"""Tests for `eval_run.py --real` CLI behaviour.

Deterministic tests (always run) cover the "no silent fallback" contract at
the CLI entry point. The live test (skipped cleanly without a local Ollama
runtime) exercises a real, small, end-to-end real-embedding run through the
CLI itself, not just the underlying library functions already covered by
tests/test_ollama_embedding_provider.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, EvaluationCase, EvaluationDataset, Membership, Organisation, User, Workspace
from app.operations import eval_run

_OLLAMA_BASE_URL = "http://localhost:11434"


def _ollama_reachable() -> bool:
    try:
        return httpx.get(f"{_OLLAMA_BASE_URL}/api/tags", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


def _configured_embedding_model() -> str | None:
    try:
        response = httpx.get(f"{_OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    for model in response.json().get("models", []):
        if "embedding" in model.get("capabilities", []):
            return model.get("name", "").split(":", 1)[0]
    return None


requires_ollama = pytest.mark.skipif(not _ollama_reachable(), reason="No local Ollama runtime reachable - skipping live --real CLI test.")


def test_eval_run_cli_real_fails_clearly_when_eval_embedding_not_configured(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    for name in ["EVAL_EMBEDDING_PROVIDER", "EVAL_EMBEDDING_MODEL"]:
        monkeypatch.delenv(name, raising=False)

    exit_code = eval_run.main([
        "--dataset", "does-not-matter", "--assistant", "does-not-matter",
        "--organisation", "does-not-matter", "--workspace", "does-not-matter",
        "--real",
    ])

    assert exit_code == 2
    assert "Cannot run with --real" in capsys.readouterr().err


def test_eval_run_cli_real_fails_clearly_when_model_unset(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("EVAL_EMBEDDING_PROVIDER", "ollama")
    monkeypatch.delenv("EVAL_EMBEDDING_MODEL", raising=False)

    exit_code = eval_run.main([
        "--dataset", "does-not-matter", "--assistant", "does-not-matter",
        "--organisation", "does-not-matter", "--workspace", "does-not-matter",
        "--real",
    ])

    assert exit_code == 2
    assert "EVAL_EMBEDDING_MODEL" in capsys.readouterr().err


def test_eval_run_cli_real_fails_clearly_when_ollama_unreachable(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("EVAL_EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("EVAL_EMBEDDING_MODEL", "whatever-model")
    monkeypatch.setenv("EVAL_EMBEDDING_BASE_URL", "http://localhost:1")

    exit_code = eval_run.main([
        "--dataset", "does-not-matter", "--assistant", "does-not-matter",
        "--organisation", "does-not-matter", "--workspace", "does-not-matter",
        "--real",
    ])

    assert exit_code == 2
    assert "Could not reach Ollama" in capsys.readouterr().err


@requires_ollama
def test_eval_run_cli_real_runs_a_small_dataset_end_to_end(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    model_name = _configured_embedding_model()
    if model_name is None:
        pytest.skip("No embedding-capable model installed in the local Ollama runtime.")

    probe = httpx.post(f"{_OLLAMA_BASE_URL}/api/embed", json={"model": model_name, "input": "probe"}, timeout=30.0)
    probe.raise_for_status()
    dimension = len(probe.json()["embeddings"][0])

    # A real (file-based) SQLite database, not `:memory:`: the evaluation
    # engine's shadow session (see app.evaluation.shadow_session) opens its
    # own separate engine from `settings.DATABASE_URL` to call the real
    # orchestrator - an in-memory SQLite URL would give that second engine an
    # entirely different, empty database, since each new `:memory:`
    # connection is isolated. `settings.DATABASE_URL` is monkeypatched to
    # match so the shadow session finds the same seeded data.
    db_url = f"sqlite:///{tmp_path / 'real-cli-test.db'}"
    original_database_url = settings.DATABASE_URL
    object.__setattr__(settings, "DATABASE_URL", db_url)  # settings is a frozen dataclass; restored in the finally block below.
    try:
        _run_real_cli_case(db_url, model_name, dimension, monkeypatch, capsys)
    finally:
        object.__setattr__(settings, "DATABASE_URL", original_database_url)


def _run_real_cli_case(db_url: str, model_name: str, dimension: int, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as db:
        organisation = Organisation(name="Real CLI Test Org", slug="real-cli-test-org", status="active", plan_key="starter")
        workspace = Workspace(organisation=organisation, name="Workspace", slug="real-cli-test-workspace", status="active", default_language="en")
        user = User(email="owner@example.test", full_name="Owner")
        membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
        db.add_all([organisation, workspace, user, membership])
        db.commit()

        document = Document(organisation_id=organisation.id, workspace_id=workspace.id, title="Pricing", source_type="txt", source_key="pricing.txt", status="ready")
        db.add(document)
        db.flush()
        version = DocumentVersion(organisation_id=organisation.id, workspace_id=workspace.id, document_id=document.id, version_number=1, checksum="checksum-pricing", processing_status="ready")
        db.add(version)
        db.flush()
        document.active_document_version_id = version.id
        chunk = Chunk(
            organisation_id=organisation.id, workspace_id=workspace.id, document_id=document.id, document_version_id=version.id,
            chunk_index=0, content="The Team plan costs $29 per month and includes 1TB of storage.", content_hash="hash-pricing",
            token_count=12, source_type="txt", source_title="Pricing", status="ready",
            embedding_provider="ollama", embedding_model=model_name, embedding_dimension=dimension, embedding_created_at=datetime.now(timezone.utc),
        )
        db.add(chunk)
        db.commit()

        widget = create_widget(
            db, organisation_id=organisation.id, workspace_id=workspace.id, display_name="Real CLI Assistant",
            environment="development", actor_user_id=user.id, initial_configuration={"knowledge_scope_json": [document.id]},
        )

        dataset = EvaluationDataset(organisation_id=organisation.id, workspace_id=workspace.id, widget_id=widget.id, name="Real CLI dataset", version="1", status="active")
        db.add(dataset)
        db.flush()
        db.add(EvaluationCase(
            dataset_id=dataset.id, organisation_id=organisation.id, workspace_id=workspace.id,
            question="How much does the Team plan cost?", expected_document_ids=[document.id],
            expected_answerability="answerable", category="answerable_factual",
        ))
        db.commit()
        db.refresh(dataset)
        dataset_id, widget_id, organisation_id_str, workspace_id_str = dataset.id, widget.id, organisation.id, workspace.id

    monkeypatch.setattr(eval_run, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setenv("EVAL_EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("EVAL_EMBEDDING_MODEL", model_name)
    monkeypatch.setenv("EVAL_EMBEDDING_DIMENSION", str(dimension))

    exit_code = eval_run.main([
        "--dataset", dataset_id, "--assistant", widget_id,
        "--organisation", organisation_id_str, "--workspace", workspace_id_str,
        "--real", "--case-timeout", "60", "--format", "json",
    ])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"total_cases": 1' in output
    assert '"passed_cases": 1' in output
    engine.dispose()
