from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, EvaluationCase, EvaluationDataset, Organisation, User, Workspace
from app.db.models.prompt import LAYER_ASSISTANT_PERSONA_TONE
from app.evaluation.categories import Answerability, CaseCategory
from app.evaluation.prompt_promotion_gate import evaluate_prompt_candidate
from app.repositories import prompt_repository as repo


@pytest.fixture()
def db_url(tmp_path) -> str:
    # File-based, not `:memory:` - app.evaluation.shadow_session opens a
    # brand-new connection for each case (defaulting to settings.DATABASE_URL
    # when shadow_database_url is None), which would see an empty in-memory
    # database rather than this fixture's seeded data. See
    # tests/test_evaluation_engine.py's identical db_url fixture.
    return f"sqlite:///{tmp_path / 'prompt-gate.db'}"


@pytest.fixture()
def db_session(db_url: str):
    original_provider = settings.EMBEDDING_PROVIDER
    original_model = settings.EMBEDDING_MODEL
    original_dimension = settings.EMBEDDING_DIMENSION
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "prompt-gate-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)

    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()

    object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
    object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
    object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)


def _seed(db: Session, *, suffix: str):
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
        embedding_provider="local-mock", embedding_model="prompt-gate-test", embedding_dimension=8,
        embedding_created_at=datetime.now(timezone.utc),
    ))
    db.commit()

    widget = create_widget(db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user.id, initial_configuration={"knowledge_scope_json": [document.id]})

    dataset = EvaluationDataset(organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, name="Gate dataset", version="1", status="active")
    db.add(dataset)
    db.flush()
    db.add(EvaluationCase(
        dataset_id=dataset.id, organisation_id=org.id, workspace_id=workspace.id,
        question="When do applications close?", expected_document_ids=[document.id],
        expected_answerability=Answerability.ANSWERABLE.value, category=CaseCategory.ANSWERABLE_FACTUAL.value,
    ))
    db.commit()
    db.refresh(dataset)

    return org, workspace, widget, dataset, user.id


def test_candidate_gate_passes_for_a_benign_persona_change(db_session: Session, db_url: str) -> None:
    org, workspace, widget, dataset, user_id = _seed(db_session, suffix="pass")
    repo.get_or_create_platform_core_template(db_session)
    persona_template = repo.get_or_create_workspace_template(db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona")
    candidate = repo.create_draft_version(db_session, template=persona_template, content="Be friendly and concise.", variables_schema=[], author_user_id=user_id)

    result = evaluate_prompt_candidate(
        db_session, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, dataset=dataset, candidate_version_id=candidate.id,
        shadow_database_url=db_url,
    )

    assert result.verdict.passed is True, result.verdict.reasons
    assert result.candidate_run_id
    assert result.baseline_run_id is None  # no prior non-candidate baseline run exists yet


def test_gate_run_recorded_prompt_version_id_matches_candidate(db_session: Session, db_url: str) -> None:
    org, workspace, widget, dataset, user_id = _seed(db_session, suffix="match")
    repo.get_or_create_platform_core_template(db_session)
    persona_template = repo.get_or_create_workspace_template(db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona")
    candidate = repo.create_draft_version(db_session, template=persona_template, content="Be terse.", variables_schema=[], author_user_id=user_id)

    result = evaluate_prompt_candidate(
        db_session, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, dataset=dataset, candidate_version_id=candidate.id,
        shadow_database_url=db_url,
    )

    from app.repositories import evaluation_repository

    run = evaluation_repository.get_run(db_session, organisation_id=org.id, workspace_id=workspace.id, run_id=result.candidate_run_id)
    assert run.prompt_version_id == candidate.id


def test_gate_reports_a_failing_verdict_for_a_nonexistent_candidate(db_session: Session, db_url: str) -> None:
    """A bogus candidate id is not an integrity mismatch (the run faithfully
    records that id as what was requested) - it manifests as every case
    failing to resolve the prompt, which the gate correctly reports as
    FAILED, not as an exception. PromptGateIntegrityError is reserved for the
    narrower case where the run's recorded identity silently diverged from
    what was actually requested."""
    org, workspace, widget, dataset, _user_id = _seed(db_session, suffix="badcandidate")
    result = evaluate_prompt_candidate(
        db_session, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, dataset=dataset, candidate_version_id="does-not-exist",
        shadow_database_url=db_url,
    )
    assert result.verdict.passed is False
    assert result.verdict.reasons


def test_gate_raises_if_the_run_did_not_actually_record_the_requested_candidate(db_session: Session, db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit-level check of the integrity guard itself (see design decision 6
    in docs/architecture/prompts.md): if run_evaluation ever returned a run
    whose prompt_version_id diverged from what was requested - a genuine bug,
    not user error - the gate must hard-fail rather than silently trust it."""
    org, workspace, widget, dataset, user_id = _seed(db_session, suffix="integrity")
    repo.get_or_create_platform_core_template(db_session)
    persona_template = repo.get_or_create_workspace_template(db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona")
    candidate = repo.create_draft_version(db_session, template=persona_template, content="Be brief.", variables_schema=[], author_user_id=user_id)

    import app.evaluation.prompt_promotion_gate as gate_module

    def _fake_run_evaluation(db, *, dataset, organisation_id, workspace_id, widget_id, options):
        from app.repositories import evaluation_repository

        run = evaluation_repository.create_run(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id, dataset=dataset,
            mode="mock", policy_snapshot={}, retrieval_settings=None, created_by=None, trigger_source="prompt_gate",
        )
        run = evaluation_repository.mark_run_started(db, run=run)
        return evaluation_repository.mark_run_completed(
            db, run=run, status="completed", total_cases=0, passed_cases=0, failed_cases=0, hard_failure_cases=0,
            provider_key=None, model_key=None, provider_model_name=None, prompt_key=None, prompt_version=None, prompt_hash=None,
            prompt_version_id="a-different-version-id",
        )

    monkeypatch.setattr(gate_module, "run_evaluation", _fake_run_evaluation)

    with pytest.raises(gate_module.PromptGateIntegrityError):
        evaluate_prompt_candidate(
            db_session, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, dataset=dataset, candidate_version_id=candidate.id,
            shadow_database_url=db_url,
        )
