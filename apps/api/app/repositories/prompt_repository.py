"""Repository for the versioned prompt-management system (templates,
versions, deployments, experiments, audit trail). Plain functions, `db:
Session` first, following the shape of
app.repositories.evaluation_candidate_repository - custom exceptions for
domain errors instead of sentinel returns, writes commit immediately.

Platform-scoped rows (organisation_id and workspace_id both NULL) are new
territory for this codebase's tenant-isolation convention: read functions
here use an explicit `(org=:org AND ws=:ws) OR (org IS NULL AND ws IS NULL)`
clause rather than the blanket organisation_id+workspace_id filter used
everywhere else - see docs/architecture/prompts.md's security-policy section.
"""

from __future__ import annotations

import difflib
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.models.prompt import (
    LAYER_PLATFORM_CORE,
    PLATFORM_IMMUTABLE_LAYERS,
    PromptAuditEvent,
    PromptDeployment,
    PromptExperiment,
    PromptTemplate,
    PromptVersion,
)
from app.prompts import defaults as prompt_defaults
from app.prompts.render import PromptVariableSpec, layer_checksum, validate_layer_content, variables_schema_to_json
from app.prompts.resolution import invalidate_cache

# --- domain exceptions -------------------------------------------------------


class TemplateNotFound(LookupError):
    pass


class VersionNotFound(LookupError):
    pass


class DeploymentNotFound(LookupError):
    pass


class ExperimentNotFound(LookupError):
    pass


class InvalidVersionTransition(ValueError):
    pass


class VersionNotApproved(ValueError):
    pass


class NoRollbackTarget(ValueError):
    pass


class LayerScopeMismatch(ValueError):
    pass


class PlatformLayerRequiresSuperAdmin(PermissionError):
    pass


class ExperimentNotGated(ValueError):
    pass


_PRE_DEPLOY_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"under_evaluation"},
    "under_evaluation": {"approved", "rejected", "draft"},
    "approved": {"rejected"},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _write_audit_event(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_user_id: str | None,
    organisation_id: str | None,
    workspace_id: str | None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> PromptAuditEvent:
    event = PromptAuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_user_id=actor_user_id,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        before_json=before,
        after_json=after,
        reason=reason,
    )
    db.add(event)
    return event


def list_audit_events(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    include_platform: bool = True,
    limit: int = 100,
) -> list[PromptAuditEvent]:
    scope_clause = _tenant_or_platform_clause(PromptAuditEvent, organisation_id, workspace_id, include_platform)
    statement = select(PromptAuditEvent).where(scope_clause)
    if entity_type is not None:
        statement = statement.where(PromptAuditEvent.entity_type == entity_type)
    if entity_id is not None:
        statement = statement.where(PromptAuditEvent.entity_id == entity_id)
    statement = statement.order_by(PromptAuditEvent.created_at.desc()).limit(limit)
    return list(db.execute(statement).scalars().all())


def _tenant_or_platform_clause(model, organisation_id: str, workspace_id: str, include_platform: bool):
    tenant_clause = and_(model.organisation_id == organisation_id, model.workspace_id == workspace_id)
    if not include_platform:
        return tenant_clause
    platform_clause = and_(model.organisation_id.is_(None), model.workspace_id.is_(None))
    return or_(tenant_clause, platform_clause)


# --- templates ----------------------------------------------------------------


def get_or_create_platform_core_template(db: Session, *, owner_user_id: str | None = None) -> PromptTemplate:
    existing = db.execute(
        select(PromptTemplate).where(
            PromptTemplate.layer == LAYER_PLATFORM_CORE,
            PromptTemplate.organisation_id.is_(None),
            PromptTemplate.workspace_id.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    template = PromptTemplate(
        organisation_id=None,
        workspace_id=None,
        layer=LAYER_PLATFORM_CORE,
        name="Platform Core Policy",
        description="Immutable platform safety policy, RAG answer policy, citation/grounding requirements, and structured output schema.",
        owner_user_id=owner_user_id,
        is_platform_immutable=True,
    )
    db.add(template)
    db.flush()
    seed_version = _create_version_row(
        db,
        template=template,
        content=prompt_defaults.PLATFORM_CORE_DEFAULT_CONTENT,
        variables_schema=prompt_defaults.PLATFORM_CORE_VARIABLES,
        author_user_id=owner_user_id,
        change_notes="Initial platform_core version seeded from the code-defined default.",
        status="approved",
    )
    seed_version.approved_at = _now()
    seed_version.approved_by_user_id = owner_user_id
    db.add(seed_version)
    db.commit()
    db.refresh(template)
    deploy_version(
        db, version=seed_version, template=template, organisation_id=None, workspace_id=None, widget_id=None, actor_user_id=owner_user_id,
    )
    db.refresh(template)
    return template


def get_or_create_workspace_template(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    layer: str,
    name: str,
    owner_user_id: str | None = None,
) -> PromptTemplate:
    if layer in PLATFORM_IMMUTABLE_LAYERS:
        raise LayerScopeMismatch(f"Layer {layer!r} is platform-immutable and cannot have a workspace-scoped template.")
    existing = db.execute(
        select(PromptTemplate).where(
            PromptTemplate.layer == layer,
            PromptTemplate.organisation_id == organisation_id,
            PromptTemplate.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    template = PromptTemplate(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        layer=layer,
        name=name,
        owner_user_id=owner_user_id,
        is_platform_immutable=False,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def list_templates(db: Session, *, organisation_id: str, workspace_id: str, include_platform: bool = True) -> list[PromptTemplate]:
    scope_clause = _tenant_or_platform_clause(PromptTemplate, organisation_id, workspace_id, include_platform)
    statement = select(PromptTemplate).where(scope_clause).order_by(PromptTemplate.layer)
    return list(db.execute(statement).scalars().all())


def get_template(db: Session, *, organisation_id: str, workspace_id: str, template_id: str, include_platform: bool = True) -> PromptTemplate | None:
    scope_clause = _tenant_or_platform_clause(PromptTemplate, organisation_id, workspace_id, include_platform)
    statement = select(PromptTemplate).where(PromptTemplate.id == template_id, scope_clause)
    return db.execute(statement).scalar_one_or_none()


def safe_template_summary(template: PromptTemplate, *, reveal_full_content: bool) -> dict:
    """Never expose full immutable-platform-layer content to a non-super-admin
    caller - see docs/architecture/prompts.md's security-policy section. Non-
    immutable (workspace) templates always reveal full content to their own
    tenant since that's the org's own authored guidance."""
    summary = {
        "id": template.id,
        "layer": template.layer,
        "name": template.name,
        "description": template.description,
        "is_platform_immutable": template.is_platform_immutable,
        "organisation_id": template.organisation_id,
        "workspace_id": template.workspace_id,
    }
    if template.is_platform_immutable and not reveal_full_content:
        summary["content_visibility"] = "summary_only"
    else:
        summary["content_visibility"] = "full"
    return summary


def safe_version_summary(version: PromptVersion, *, template: PromptTemplate, reveal_full_content: bool) -> dict:
    """Same visibility rule as safe_template_summary, applied per-version -
    the content/checksum of an immutable-platform-layer version is never
    returned to a non-super-admin caller, only its lifecycle metadata."""
    summary = {
        "id": version.id,
        "template_id": version.template_id,
        "version_number": version.version_number,
        "status": version.status,
        "author_user_id": version.author_user_id,
        "change_notes": version.change_notes,
        "parent_version_id": version.parent_version_id,
        "approved_at": version.approved_at,
        "approved_by_user_id": version.approved_by_user_id,
        "published_at": version.published_at,
        "created_at": version.created_at,
        "updated_at": version.updated_at,
    }
    reveal = reveal_full_content or not template.is_platform_immutable
    summary["content_visibility"] = "full" if reveal else "summary_only"
    summary["content"] = version.content if reveal else None
    summary["checksum"] = version.checksum if reveal else None
    summary["variables_schema_json"] = version.variables_schema_json if reveal else None
    return summary


# --- versions -------------------------------------------------------------


def _next_version_number(db: Session, *, template_id: str) -> int:
    current_max = db.execute(select(func.max(PromptVersion.version_number)).where(PromptVersion.template_id == template_id)).scalar_one()
    return (current_max or 0) + 1


def _create_version_row(
    db: Session,
    *,
    template: PromptTemplate,
    content: str,
    variables_schema: list[PromptVariableSpec],
    author_user_id: str | None,
    change_notes: str | None,
    parent_version_id: str | None = None,
    status: str = "draft",
) -> PromptVersion:
    validate_layer_content(content, variables_schema)
    version_number = _next_version_number(db, template_id=template.id)
    checksum = layer_checksum(layer=template.layer, version_number=version_number, content=content, variables_schema=variables_schema)
    version = PromptVersion(
        template_id=template.id,
        version_number=version_number,
        content=content,
        variables_schema_json=variables_schema_to_json(variables_schema),
        checksum=checksum,
        status=status,
        author_user_id=author_user_id,
        change_notes=change_notes,
        parent_version_id=parent_version_id,
    )
    db.add(version)
    db.flush()
    return version


def create_draft_version(
    db: Session,
    *,
    template: PromptTemplate,
    content: str,
    variables_schema: list[PromptVariableSpec] | None,
    author_user_id: str | None,
    change_notes: str | None = None,
    parent_version_id: str | None = None,
) -> PromptVersion:
    schema = variables_schema if variables_schema is not None else prompt_defaults.DEFAULT_LAYER_VARIABLES.get(template.layer, [])
    version = _create_version_row(
        db, template=template, content=content, variables_schema=schema, author_user_id=author_user_id,
        change_notes=change_notes, parent_version_id=parent_version_id, status="draft",
    )
    _write_audit_event(
        db, entity_type="prompt_version", entity_id=version.id, action="created", actor_user_id=author_user_id,
        organisation_id=template.organisation_id, workspace_id=template.workspace_id,
        after={"status": version.status, "version_number": version.version_number, "checksum": version.checksum},
    )
    db.commit()
    db.refresh(version)
    return version


def get_version(db: Session, *, version_id: str) -> PromptVersion | None:
    return db.get(PromptVersion, version_id)


def list_versions(db: Session, *, template_id: str) -> list[PromptVersion]:
    statement = select(PromptVersion).where(PromptVersion.template_id == template_id).order_by(PromptVersion.version_number.desc())
    return list(db.execute(statement).scalars().all())


def diff_versions(version_a: PromptVersion, version_b: PromptVersion) -> list[str]:
    return list(
        difflib.unified_diff(
            version_a.content.splitlines(),
            version_b.content.splitlines(),
            fromfile=f"v{version_a.version_number}",
            tofile=f"v{version_b.version_number}",
            lineterm="",
        )
    )


def transition_version_status(
    db: Session,
    *,
    version: PromptVersion,
    new_status: str,
    actor_user_id: str | None,
    organisation_id: str | None,
    workspace_id: str | None,
    reason: str | None = None,
) -> PromptVersion:
    allowed = _PRE_DEPLOY_TRANSITIONS.get(version.status, set())
    if new_status not in allowed:
        raise InvalidVersionTransition(f"Cannot move prompt version from {version.status!r} to {new_status!r}.")
    previous_status = version.status
    version.status = new_status
    if new_status == "approved":
        version.approved_at = _now()
        version.approved_by_user_id = actor_user_id
    db.add(version)
    _write_audit_event(
        db, entity_type="prompt_version", entity_id=version.id, action=f"status_changed:{new_status}", actor_user_id=actor_user_id,
        organisation_id=organisation_id, workspace_id=workspace_id,
        before={"status": previous_status}, after={"status": new_status}, reason=reason,
    )
    db.commit()
    db.refresh(version)
    return version


# --- deployments ----------------------------------------------------------


def get_deployment(db: Session, *, deployment_id: str) -> PromptDeployment | None:
    return db.get(PromptDeployment, deployment_id)


def get_active_deployment(
    db: Session, *, layer: str, organisation_id: str | None, workspace_id: str | None, widget_id: str | None
) -> PromptDeployment | None:
    statement = select(PromptDeployment).where(
        PromptDeployment.layer == layer,
        PromptDeployment.organisation_id.is_(organisation_id) if organisation_id is None else PromptDeployment.organisation_id == organisation_id,
        PromptDeployment.workspace_id.is_(workspace_id) if workspace_id is None else PromptDeployment.workspace_id == workspace_id,
        PromptDeployment.widget_id.is_(widget_id) if widget_id is None else PromptDeployment.widget_id == widget_id,
    )
    return db.execute(statement).scalar_one_or_none()


def deploy_version(
    db: Session,
    *,
    version: PromptVersion,
    template: PromptTemplate,
    organisation_id: str | None,
    workspace_id: str | None,
    widget_id: str | None,
    actor_user_id: str | None,
    rollout_percentage: int = 100,
) -> PromptDeployment:
    if template.id != version.template_id:
        raise LayerScopeMismatch("Version does not belong to the given template.")
    if template.is_platform_immutable and (organisation_id is not None or workspace_id is not None or widget_id is not None):
        raise LayerScopeMismatch("Platform-immutable layers may only be deployed platform-wide (no org/workspace/widget scope).")
    if not template.is_platform_immutable and widget_id is None:
        raise LayerScopeMismatch("Non-platform layers must be deployed to a specific widget.")
    if version.status != "approved":
        raise VersionNotApproved(f"Prompt version {version.id} must be status='approved' before deployment (is {version.status!r}).")

    existing = get_active_deployment(db, layer=template.layer, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    previous_version_id = None
    if existing is not None:
        previous_version = db.get(PromptVersion, existing.active_version_id)
        if previous_version is not None and previous_version.status == "active":
            previous_version.status = "superseded"
            db.add(previous_version)
        previous_version_id = existing.active_version_id
        existing.active_version_id = version.id
        existing.previous_version_id = previous_version_id
        existing.rollout_percentage = rollout_percentage
        existing.deployed_by_user_id = actor_user_id
        deployment = existing
    else:
        deployment = PromptDeployment(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            widget_id=widget_id,
            layer=template.layer,
            active_version_id=version.id,
            previous_version_id=None,
            rollout_percentage=rollout_percentage,
            deployed_by_user_id=actor_user_id,
        )

    version.status = "active"
    version.published_at = version.published_at or _now()
    db.add(version)
    db.add(deployment)
    db.flush()

    _write_audit_event(
        db, entity_type="prompt_deployment", entity_id=deployment.id, action="deployed", actor_user_id=actor_user_id,
        organisation_id=organisation_id, workspace_id=workspace_id,
        before={"previous_version_id": previous_version_id}, after={"active_version_id": version.id},
    )
    db.commit()
    db.refresh(deployment)
    invalidate_cache(widget_id)
    return deployment


def rollback_deployment(
    db: Session,
    *,
    deployment: PromptDeployment,
    actor_user_id: str | None,
    reason: str | None = None,
) -> PromptDeployment:
    if deployment.previous_version_id is None:
        raise NoRollbackTarget(f"Deployment {deployment.id} has no previous version to roll back to.")

    failed_version = db.get(PromptVersion, deployment.active_version_id)
    restored_version = db.get(PromptVersion, deployment.previous_version_id)
    if restored_version is None:
        raise NoRollbackTarget(f"Rollback target version {deployment.previous_version_id} no longer exists.")

    if failed_version is not None:
        failed_version.status = "rolled_back"
        db.add(failed_version)
    restored_version.status = "active"
    db.add(restored_version)

    deployment.previous_version_id = deployment.active_version_id
    deployment.active_version_id = restored_version.id
    deployment.deployed_by_user_id = actor_user_id
    db.add(deployment)
    db.flush()

    _write_audit_event(
        db, entity_type="prompt_deployment", entity_id=deployment.id, action="rolled_back", actor_user_id=actor_user_id,
        organisation_id=deployment.organisation_id, workspace_id=deployment.workspace_id,
        before={"active_version_id": failed_version.id if failed_version else None},
        after={"active_version_id": restored_version.id}, reason=reason,
    )
    db.commit()
    db.refresh(deployment)
    invalidate_cache(deployment.widget_id)
    return deployment


# --- experiments ------------------------------------------------------------


def create_experiment(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    widget_id: str,
    layer: str,
    control_version_id: str,
    candidate_version_id: str,
    traffic_allocation_percentage: int,
    created_by_user_id: str | None,
    is_super_admin: bool,
    success_criteria: dict | None = None,
    evaluation_dataset_id: str | None = None,
    max_duration_hours: int | None = None,
) -> PromptExperiment:
    if layer in PLATFORM_IMMUTABLE_LAYERS and not is_super_admin:
        raise PlatformLayerRequiresSuperAdmin("Experiments on platform-immutable layers require a super admin.")
    experiment = PromptExperiment(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget_id,
        layer=layer,
        control_version_id=control_version_id,
        candidate_version_id=candidate_version_id,
        traffic_allocation_percentage=max(0, min(100, traffic_allocation_percentage)),
        status="draft",
        success_criteria_json=success_criteria,
        evaluation_dataset_id=evaluation_dataset_id,
        max_duration_hours=max_duration_hours,
        safety_gate_state="pending",
        created_by_user_id=created_by_user_id,
    )
    db.add(experiment)
    db.flush()
    _write_audit_event(
        db, entity_type="prompt_experiment", entity_id=experiment.id, action="created", actor_user_id=created_by_user_id,
        organisation_id=organisation_id, workspace_id=workspace_id,
        after={"layer": layer, "candidate_version_id": candidate_version_id, "control_version_id": control_version_id},
    )
    db.commit()
    db.refresh(experiment)
    return experiment


def record_candidate_gate_result(db: Session, *, experiment: PromptExperiment, gate_run_id: str | None, passed: bool) -> PromptExperiment:
    experiment.candidate_gate_run_id = gate_run_id
    experiment.safety_gate_state = "passed" if passed else "failed"
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def start_experiment(db: Session, *, experiment: PromptExperiment, actor_user_id: str | None, is_super_admin: bool) -> PromptExperiment:
    if experiment.layer in PLATFORM_IMMUTABLE_LAYERS and not is_super_admin:
        raise PlatformLayerRequiresSuperAdmin("Starting an experiment on a platform-immutable layer requires a super admin.")
    if experiment.safety_gate_state != "passed":
        raise ExperimentNotGated(f"Experiment {experiment.id} cannot start before its candidate passes the evaluation gate.")
    experiment.status = "running"
    if experiment.start_at is None:
        experiment.start_at = _now()
    if experiment.end_at is None and experiment.max_duration_hours is not None:
        from datetime import timedelta

        experiment.end_at = experiment.start_at + timedelta(hours=experiment.max_duration_hours)
    db.add(experiment)
    _write_audit_event(
        db, entity_type="prompt_experiment", entity_id=experiment.id, action="started", actor_user_id=actor_user_id,
        organisation_id=experiment.organisation_id, workspace_id=experiment.workspace_id,
        after={"status": "running", "start_at": experiment.start_at.isoformat() if experiment.start_at else None},
    )
    db.commit()
    db.refresh(experiment)
    return experiment


def kill_experiment(db: Session, *, experiment: PromptExperiment, actor_user_id: str | None, reason: str | None = None) -> PromptExperiment:
    experiment.status = "killed"
    experiment.end_at = _now()
    db.add(experiment)
    _write_audit_event(
        db, entity_type="prompt_experiment", entity_id=experiment.id, action="killed", actor_user_id=actor_user_id,
        organisation_id=experiment.organisation_id, workspace_id=experiment.workspace_id,
        after={"status": "killed"}, reason=reason,
    )
    db.commit()
    db.refresh(experiment)
    return experiment


def complete_experiment(db: Session, *, experiment: PromptExperiment, actor_user_id: str | None) -> PromptExperiment:
    experiment.status = "completed"
    if experiment.end_at is None:
        experiment.end_at = _now()
    db.add(experiment)
    _write_audit_event(
        db, entity_type="prompt_experiment", entity_id=experiment.id, action="completed", actor_user_id=actor_user_id,
        organisation_id=experiment.organisation_id, workspace_id=experiment.workspace_id,
        after={"status": "completed"},
    )
    db.commit()
    db.refresh(experiment)
    return experiment


def get_experiment(db: Session, *, experiment_id: str) -> PromptExperiment | None:
    return db.get(PromptExperiment, experiment_id)


def list_experiments_for_widget(db: Session, *, widget_id: str) -> list[PromptExperiment]:
    statement = select(PromptExperiment).where(PromptExperiment.widget_id == widget_id).order_by(PromptExperiment.created_at.desc())
    return list(db.execute(statement).scalars().all())
