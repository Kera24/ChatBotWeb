from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.db.base import Base
from app.db.models import Organisation, User, Workspace
from app.db.models.prompt import LAYER_ASSISTANT_PERSONA_TONE, LAYER_ORGANISATION_GUIDANCE, LAYER_PLATFORM_CORE
from app.prompts import defaults as prompt_defaults
from app.repositories import prompt_repository as repo


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant(db: Session, *, suffix: str):
    unique = uuid4().hex[:8]
    org = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}-{unique}", status="active")
    workspace = Workspace(organisation=org, name="Workspace", slug=f"workspace-{suffix}-{unique}", status="active")
    user = User(email=f"owner-{suffix}-{unique}@example.test")
    db.add_all([org, workspace, user])
    db.commit()
    widget = create_widget(db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=user.id)
    return org, workspace, widget, user.id


def test_platform_core_bootstrap_is_idempotent(db_session: Session) -> None:
    first = repo.get_or_create_platform_core_template(db_session)
    second = repo.get_or_create_platform_core_template(db_session)
    assert first.id == second.id
    assert first.is_platform_immutable is True

    versions = repo.list_versions(db_session, template_id=first.id)
    assert len(versions) == 1
    assert versions[0].status == "active"

    deployment = repo.get_active_deployment(db_session, layer=LAYER_PLATFORM_CORE, organisation_id=None, workspace_id=None, widget_id=None)
    assert deployment is not None
    assert deployment.active_version_id == versions[0].id


def test_draft_to_deploy_lifecycle(db_session: Session) -> None:
    org, workspace, widget, user_id = _seed_tenant(db_session, suffix="lifecycle")
    template = repo.get_or_create_workspace_template(
        db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona"
    )
    draft = repo.create_draft_version(db_session, template=template, content="Be friendly.", variables_schema=[], author_user_id=user_id)
    assert draft.status == "draft"
    assert draft.version_number == 1

    with pytest.raises(repo.VersionNotApproved):
        repo.deploy_version(db_session, version=draft, template=template, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, actor_user_id=user_id)

    under_eval = repo.transition_version_status(db_session, version=draft, new_status="under_evaluation", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
    approved = repo.transition_version_status(db_session, version=under_eval, new_status="approved", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
    assert approved.approved_at is not None

    with pytest.raises(repo.InvalidVersionTransition):
        repo.transition_version_status(db_session, version=approved, new_status="under_evaluation", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)

    deployment = repo.deploy_version(db_session, version=approved, template=template, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, actor_user_id=user_id)
    assert deployment.active_version_id == approved.id
    db_session.refresh(approved)
    assert approved.status == "active"


def test_deploy_rejects_platform_scope_for_workspace_layer(db_session: Session) -> None:
    org, workspace, widget, user_id = _seed_tenant(db_session, suffix="scope")
    template = repo.get_or_create_workspace_template(
        db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ORGANISATION_GUIDANCE, name="Guidance"
    )
    draft = repo.create_draft_version(db_session, template=template, content="Be precise.", variables_schema=[], author_user_id=user_id)
    under_eval = repo.transition_version_status(db_session, version=draft, new_status="under_evaluation", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
    approved = repo.transition_version_status(db_session, version=under_eval, new_status="approved", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)

    with pytest.raises(repo.LayerScopeMismatch):
        repo.deploy_version(db_session, version=approved, template=template, organisation_id=org.id, workspace_id=workspace.id, widget_id=None, actor_user_id=user_id)


def test_rollback_restores_previous_version_without_deleting_failed_one(db_session: Session) -> None:
    org, workspace, widget, user_id = _seed_tenant(db_session, suffix="rollback")
    template = repo.get_or_create_workspace_template(
        db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona"
    )

    def _approve(content: str):
        draft = repo.create_draft_version(db_session, template=template, content=content, variables_schema=[], author_user_id=user_id)
        under_eval = repo.transition_version_status(db_session, version=draft, new_status="under_evaluation", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
        return repo.transition_version_status(db_session, version=under_eval, new_status="approved", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)

    v1 = _approve("Warm and concise.")
    deployment = repo.deploy_version(db_session, version=v1, template=template, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, actor_user_id=user_id)

    v2 = _approve("Extremely verbose.")
    deployment = repo.deploy_version(db_session, version=v2, template=template, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, actor_user_id=user_id)
    assert deployment.active_version_id == v2.id
    assert deployment.previous_version_id == v1.id

    rolled_back = repo.rollback_deployment(db_session, deployment=deployment, actor_user_id=user_id, reason="v2 too verbose")
    assert rolled_back.active_version_id == v1.id

    db_session.refresh(v1)
    db_session.refresh(v2)
    assert v1.status == "active"
    assert v2.status == "rolled_back"

    # Never deleted - still fetchable.
    assert repo.get_version(db_session, version_id=v2.id) is not None

    # A second rollback swaps back to v2 - previous_version_id is never None
    # after a first deployment, so this is a valid "undo the undo," not an
    # error. NoRollbackTarget only fires when there is truly nothing to roll
    # back to - a deployment that has only ever been deployed once.
    other_template = repo.get_or_create_workspace_template(
        db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ORGANISATION_GUIDANCE, name="Guidance"
    )
    draft = repo.create_draft_version(db_session, template=other_template, content="Answer precisely.", variables_schema=[], author_user_id=user_id)
    under_eval = repo.transition_version_status(db_session, version=draft, new_status="under_evaluation", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
    approved = repo.transition_version_status(db_session, version=under_eval, new_status="approved", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)
    first_deployment = repo.deploy_version(db_session, version=approved, template=other_template, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, actor_user_id=user_id)
    assert first_deployment.previous_version_id is None
    with pytest.raises(repo.NoRollbackTarget):
        repo.rollback_deployment(db_session, deployment=first_deployment, actor_user_id=user_id)


def test_null_scoped_visibility_matrix(db_session: Session) -> None:
    repo.get_or_create_platform_core_template(db_session)
    org_a, workspace_a, _widget_a, user_a = _seed_tenant(db_session, suffix="tenant-a")
    org_b, workspace_b, _widget_b, _user_b = _seed_tenant(db_session, suffix="tenant-b")

    repo.get_or_create_workspace_template(
        db_session, organisation_id=org_a.id, workspace_id=workspace_a.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Tenant A Persona"
    )

    tenant_a_templates = repo.list_templates(db_session, organisation_id=org_a.id, workspace_id=workspace_a.id)
    layers_a = {t.layer for t in tenant_a_templates}
    assert LAYER_PLATFORM_CORE in layers_a
    assert LAYER_ASSISTANT_PERSONA_TONE in layers_a

    tenant_b_templates = repo.list_templates(db_session, organisation_id=org_b.id, workspace_id=workspace_b.id)
    layers_b = {t.layer for t in tenant_b_templates}
    assert LAYER_PLATFORM_CORE in layers_b, "platform layer must be visible to every tenant"
    assert LAYER_ASSISTANT_PERSONA_TONE not in layers_b, "tenant A's workspace template must not leak to tenant B"

    without_platform = repo.list_templates(db_session, organisation_id=org_b.id, workspace_id=workspace_b.id, include_platform=False)
    assert without_platform == []


def test_safe_summary_hides_platform_content_unless_revealed(db_session: Session) -> None:
    template = repo.get_or_create_platform_core_template(db_session)
    hidden = repo.safe_template_summary(template, reveal_full_content=False)
    assert hidden["content_visibility"] == "summary_only"

    revealed = repo.safe_template_summary(template, reveal_full_content=True)
    assert revealed["content_visibility"] == "full"

    version = repo.list_versions(db_session, template_id=template.id)[0]
    hidden_version = repo.safe_version_summary(version, template=template, reveal_full_content=False)
    assert hidden_version["content"] is None
    assert hidden_version["checksum"] is None

    revealed_version = repo.safe_version_summary(version, template=template, reveal_full_content=True)
    assert revealed_version["content"] is not None


def test_experiment_on_platform_layer_requires_super_admin(db_session: Session) -> None:
    org, workspace, widget, user_id = _seed_tenant(db_session, suffix="experiment")
    template = repo.get_or_create_platform_core_template(db_session)
    versions = repo.list_versions(db_session, template_id=template.id)
    active_version = versions[0]
    candidate = repo.create_draft_version(
        db_session, template=template, content=active_version.content, variables_schema=prompt_defaults.PLATFORM_CORE_VARIABLES, author_user_id=user_id
    )

    with pytest.raises(repo.PlatformLayerRequiresSuperAdmin):
        repo.create_experiment(
            db_session, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, layer=LAYER_PLATFORM_CORE,
            control_version_id=active_version.id, candidate_version_id=candidate.id, traffic_allocation_percentage=10,
            created_by_user_id=user_id, is_super_admin=False,
        )

    experiment = repo.create_experiment(
        db_session, organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, layer=LAYER_PLATFORM_CORE,
        control_version_id=active_version.id, candidate_version_id=candidate.id, traffic_allocation_percentage=10,
        created_by_user_id=user_id, is_super_admin=True,
    )
    assert experiment.safety_gate_state == "pending"

    with pytest.raises(repo.ExperimentNotGated):
        repo.start_experiment(db_session, experiment=experiment, actor_user_id=user_id, is_super_admin=True)

    repo.record_candidate_gate_result(db_session, experiment=experiment, gate_run_id=None, passed=True)
    started = repo.start_experiment(db_session, experiment=experiment, actor_user_id=user_id, is_super_admin=True)
    assert started.status == "running"

    killed = repo.kill_experiment(db_session, experiment=started, actor_user_id=user_id, reason="incident")
    assert killed.status == "killed"
    assert killed.end_at is not None


def test_audit_trail_records_every_mutation(db_session: Session) -> None:
    org, workspace, widget, user_id = _seed_tenant(db_session, suffix="audit")
    template = repo.get_or_create_workspace_template(
        db_session, organisation_id=org.id, workspace_id=workspace.id, layer=LAYER_ASSISTANT_PERSONA_TONE, name="Persona"
    )
    draft = repo.create_draft_version(db_session, template=template, content="Be kind.", variables_schema=[], author_user_id=user_id)
    repo.transition_version_status(db_session, version=draft, new_status="under_evaluation", actor_user_id=user_id, organisation_id=org.id, workspace_id=workspace.id)

    events = repo.list_audit_events(db_session, organisation_id=org.id, workspace_id=workspace.id, include_platform=False)
    actions = {event.action for event in events}
    assert "created" in actions
    assert "status_changed:under_evaluation" in actions
    assert all(event.organisation_id == org.id for event in events)
