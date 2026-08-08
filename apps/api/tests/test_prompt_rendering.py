from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.errors import PromptValidationError
from app.access.widget_admin.service import create_widget
from app.db.base import Base
from app.db.models import Organisation, User, Workspace
from app.db.models.prompt import LAYER_ASSISTANT_PERSONA_TONE, LAYER_ORGANISATION_GUIDANCE
from app.prompts.render import (
    DEFAULT_MAX_LAYER_CONTENT_CHARS,
    PromptVariableSpec,
    assert_max_rendered_length,
    composite_checksum,
    composite_version_label,
    render_layer_content,
    validate_layer_content,
    validate_template_variables,
)
from app.prompts.resolution import PromptResolutionError, invalidate_cache, resolve_composite_prompt
from app.repositories import prompt_repository as repo


def test_validate_template_variables_rejects_unknown_placeholder() -> None:
    with pytest.raises(PromptValidationError):
        validate_template_variables("Hello {unknown_var}", {"question"})
    validate_template_variables("Hello {question}", {"question"})  # does not raise


def test_render_layer_content_requires_declared_required_variables() -> None:
    schema = [PromptVariableSpec("question", required=True)]
    with pytest.raises(PromptValidationError):
        render_layer_content("Q: {question}", {}, schema)
    assert render_layer_content("Q: {question}", {"question": "hi"}, schema) == "Q: hi"


def test_render_layer_content_enforces_max_length() -> None:
    schema = [PromptVariableSpec("name", required=False, max_length=5)]
    with pytest.raises(PromptValidationError):
        render_layer_content("Hi {name}", {"name": "way too long a value"}, schema)


def test_validate_layer_content_enforces_size_ceiling() -> None:
    huge = "x" * (DEFAULT_MAX_LAYER_CONTENT_CHARS + 1)
    with pytest.raises(PromptValidationError):
        validate_layer_content(huge, [])


def test_assert_max_rendered_length() -> None:
    assert_max_rendered_length("short")  # does not raise
    with pytest.raises(PromptValidationError):
        assert_max_rendered_length("x" * 100, max_chars=10)


def test_composite_version_label_and_checksum_are_deterministic() -> None:
    label = composite_version_label({"platform_core": 3, "assistant_persona_tone": 2})
    assert label == "core:v3+persona:v2"
    checksum_a = composite_checksum(["hash1", "hash2"])
    checksum_b = composite_checksum(["hash1", "hash2"])
    checksum_c = composite_checksum(["hash1", "hash3"])
    assert checksum_a == checksum_b
    assert checksum_a != checksum_c


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()
    invalidate_cache()


def _seed_tenant(db: Session, *, suffix: str):
    unique = uuid4().hex[:8]
    org = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}-{unique}", status="active")
    workspace = Workspace(organisation=org, name="Workspace", slug=f"workspace-{suffix}-{unique}", status="active")
    user = User(email=f"owner-{suffix}-{unique}@example.test")
    db.add_all([org, workspace, user])
    db.commit()
    widget = create_widget(db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user.id)
    return org, workspace, widget, user.id


def _approve_and_deploy(db: Session, *, template, content: str, org, workspace, widget, user_id):
    draft = repo.create_draft_version(db, template=template, content=content, variables_schema=[], author_user_id=user_id)
    under_eval = repo.transition_version_status(db, version=draft, new_status="under_evaluation", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
    approved = repo.transition_version_status(db, version=under_eval, new_status="approved", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
    return repo.deploy_version(db, version=approved, template=template, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, actor_user_id=user_id)


def test_dormant_scope_returns_none(db_session: Session) -> None:
    org, workspace, widget, _user_id = _seed_tenant(db_session, suffix="dormant")
    result = resolve_composite_prompt(
        db_session, prompt_key="grounded_rag_answer", organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id,
        question="q", context="c", conversation_id=None,
    )
    assert result is None


def test_composite_engages_once_platform_core_deployed(db_session: Session) -> None:
    org, workspace, widget, _user_id = _seed_tenant(db_session, suffix="platform")
    repo.get_or_create_platform_core_template(db_session)

    result = resolve_composite_prompt(
        db_session, prompt_key="grounded_rag_answer", organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id,
        question="When do applications close?", context="[1] FAQ | Applications close in March.", conversation_id="conv-1",
    )
    assert result is not None
    assert result.rendered.version == "core:v1"
    assert "Applications close in March" in result.rendered.user_prompt
    assert "{assistant_persona}" not in result.rendered.system_prompt


def test_composite_layers_persona_and_guidance_into_system_prompt(db_session: Session) -> None:
    org, workspace, widget, user_id = _seed_tenant(db_session, suffix="layered")
    repo.get_or_create_platform_core_template(db_session)
    persona_template = repo.get_or_create_workspace_template(db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona")
    guidance_template = repo.get_or_create_workspace_template(db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ORGANISATION_GUIDANCE, name="Guidance")
    _approve_and_deploy(db_session, template=persona_template, content="Sign off as Acme Support.", org=org, workspace=workspace, widget=widget, user_id=user_id)
    _approve_and_deploy(db_session, template=guidance_template, content="Refunds require an order number.", org=org, workspace=workspace, widget=widget, user_id=user_id)

    result = resolve_composite_prompt(
        db_session, prompt_key="grounded_rag_answer", organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id,
        question="What is the refund policy?", context="[1] Refunds | Refunds within 30 days.", conversation_id="conv-1",
    )
    assert "Acme Support" in result.rendered.system_prompt
    assert "order number" in result.rendered.system_prompt
    assert result.rendered.version == "core:v1+persona:v1+guidance:v1"


def test_override_id_forces_a_specific_candidate_version(db_session: Session) -> None:
    org, workspace, widget, user_id = _seed_tenant(db_session, suffix="override")
    repo.get_or_create_platform_core_template(db_session)
    persona_template = repo.get_or_create_workspace_template(db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona")
    draft = repo.create_draft_version(db_session, template=persona_template, content="Speak like a pirate.", variables_schema=[], author_user_id=user_id)

    result = resolve_composite_prompt(
        db_session, prompt_key="grounded_rag_answer", organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id,
        question="q", context="c", conversation_id=None, prompt_version_override_id=draft.id,
    )
    assert "pirate" in result.rendered.system_prompt
    assert result.resolved_layer_version_ids[LAYER_ASSISTANT_PERSONA_TONE] == draft.id


def test_override_raises_loudly_on_bad_id(db_session: Session) -> None:
    org, workspace, widget, _user_id = _seed_tenant(db_session, suffix="badoverride")
    with pytest.raises(PromptResolutionError):
        resolve_composite_prompt(
            db_session, prompt_key="grounded_rag_answer", organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id,
            question="q", context="c", conversation_id=None, prompt_version_override_id="does-not-exist",
        )


def test_cache_invalidation_reflects_new_deployment_immediately(db_session: Session) -> None:
    org, workspace, widget, user_id = _seed_tenant(db_session, suffix="cache")
    repo.get_or_create_platform_core_template(db_session)
    persona_template = repo.get_or_create_workspace_template(db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona")

    # Prime the cache with "nothing deployed for this widget's persona layer."
    first = resolve_composite_prompt(
        db_session, prompt_key="grounded_rag_answer", organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id,
        question="q", context="c", conversation_id=None,
    )
    assert "assistant_persona" not in (first.rendered.system_prompt if first else "")

    _approve_and_deploy(db_session, template=persona_template, content="Be terse.", org=org, workspace=workspace, widget=widget, user_id=user_id)

    second = resolve_composite_prompt(
        db_session, prompt_key="grounded_rag_answer", organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id,
        question="q", context="c", conversation_id=None,
    )
    assert "Be terse" in second.rendered.system_prompt, "cache must be invalidated by deploy_version, not served stale for up to 30s"
