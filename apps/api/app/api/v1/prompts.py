from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.ai.errors import PromptValidationError
from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.db.models.prompt import LAYER_PLATFORM_CORE, PLATFORM_IMMUTABLE_LAYERS, PROMPT_LAYERS
from app.evaluation.prompt_promotion_gate import PromptGateIntegrityError, evaluate_prompt_candidate
from app.prompts.experiment_metrics import compute_experiment_metrics
from app.prompts.render import PromptVariableSpec, render_layer_content, variables_schema_from_json
from app.prompts.resolution import PromptResolutionError, resolve_composite_prompt
from app.repositories import evaluation_repository, prompt_repository
from app.repositories.prompt_repository import (
    DeploymentNotFound,
    ExperimentNotFound,
    ExperimentNotGated,
    InvalidVersionTransition,
    LayerScopeMismatch,
    NoRollbackTarget,
    PlatformLayerRequiresSuperAdmin,
    TemplateNotFound,
    VersionNotApproved,
    VersionNotFound,
)
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.prompt_management import (
    PromptAuditEventRead,
    PromptDeploymentCreate,
    PromptExperimentCreate,
    PromptExperimentKill,
    PromptExperimentRead,
    PromptGateRunRequest,
    PromptRollbackRequest,
    PromptTemplateCreate,
    PromptVersionCreate,
    PromptVersionTransition,
)

router = APIRouter()

# Mirrors app.api.v1.evaluation's viewer-inclusive / owner-admin-only split.
PromptReaderDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]
PromptManagerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]


def _ensure_workspace(db: DbSession, *, organisation_id: str, workspace_id: str) -> None:
    if get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")


def _is_super_admin(current_user: DevelopmentCurrentUser) -> bool:
    return current_user.role == "super_admin"


def _template_or_404(db: DbSession, *, organisation_id: str, workspace_id: str, template_id: str):
    template = prompt_repository.get_template(db, organisation_id=organisation_id, workspace_id=workspace_id, template_id=template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found.")
    return template


def _version_or_404(db: DbSession, *, version_id: str):
    version = prompt_repository.get_version(db, version_id=version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt version not found.")
    return version


# --- templates ----------------------------------------------------------------


@router.get("/{workspace_id}/prompts/templates")
def list_templates(
    workspace_id: str,
    db: DbSession,
    current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    # Lazily bootstraps the platform_core template/version/deployment on
    # first read so the admin UI is usable without a manual seed step - this
    # is an admin-listing-only convenience and never runs on the RAG hot path
    # (app.ai.rag_orchestrator only ever reads what already exists).
    prompt_repository.get_or_create_platform_core_template(db)
    templates = prompt_repository.list_templates(db, organisation_id=organisation_id, workspace_id=workspace_id)
    reveal = _is_super_admin(current_user)
    return success_response([prompt_repository.safe_template_summary(t, reveal_full_content=reveal) for t in templates])


@router.post("/{workspace_id}/prompts/templates", status_code=status.HTTP_201_CREATED)
def create_template(
    workspace_id: str,
    payload: PromptTemplateCreate,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if payload.layer not in PROMPT_LAYERS or payload.layer in PLATFORM_IMMUTABLE_LAYERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"layer must be a customer-editable layer: {sorted(set(PROMPT_LAYERS) - set(PLATFORM_IMMUTABLE_LAYERS))}")
    try:
        template = prompt_repository.get_or_create_workspace_template(
            db, organisation_id=organisation_id, workspace_id=workspace_id, layer=payload.layer, name=payload.name, owner_user_id=current_user.user_id,
        )
    except LayerScopeMismatch as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_response(prompt_repository.safe_template_summary(template, reveal_full_content=True))


@router.get("/{workspace_id}/prompts/templates/{template_id}")
def get_template(
    workspace_id: str,
    template_id: str,
    db: DbSession,
    current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    template = _template_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, template_id=template_id)
    reveal = _is_super_admin(current_user)
    return success_response(prompt_repository.safe_template_summary(template, reveal_full_content=reveal))


# --- versions -------------------------------------------------------------


@router.get("/{workspace_id}/prompts/templates/{template_id}/versions")
def list_versions(
    workspace_id: str,
    template_id: str,
    db: DbSession,
    current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    template = _template_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, template_id=template_id)
    reveal = _is_super_admin(current_user)
    versions = prompt_repository.list_versions(db, template_id=template.id)
    return success_response([prompt_repository.safe_version_summary(v, template=template, reveal_full_content=reveal) for v in versions])


@router.post("/{workspace_id}/prompts/templates/{template_id}/versions", status_code=status.HTTP_201_CREATED)
def create_version(
    workspace_id: str,
    template_id: str,
    payload: PromptVersionCreate,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    template = _template_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, template_id=template_id)
    if template.is_platform_immutable and not _is_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editing a platform-immutable layer requires a super admin.")
    schema = [PromptVariableSpec(**spec.model_dump()) for spec in (payload.variables_schema or [])] or None
    try:
        version = prompt_repository.create_draft_version(
            db, template=template, content=payload.content, variables_schema=schema, author_user_id=current_user.user_id,
            change_notes=payload.change_notes, parent_version_id=payload.parent_version_id,
        )
    except PromptValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return success_response(prompt_repository.safe_version_summary(version, template=template, reveal_full_content=True))


@router.get("/{workspace_id}/prompts/versions/{version_id}")
def get_version(
    workspace_id: str,
    version_id: str,
    db: DbSession,
    current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    version = _version_or_404(db, version_id=version_id)
    template = _template_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, template_id=version.template_id)
    reveal = _is_super_admin(current_user)
    return success_response(prompt_repository.safe_version_summary(version, template=template, reveal_full_content=reveal))


@router.get("/{workspace_id}/prompts/versions/{version_id}/diff")
def diff_version(
    workspace_id: str,
    version_id: str,
    db: DbSession,
    current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
    against: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    version = _version_or_404(db, version_id=version_id)
    other = _version_or_404(db, version_id=against)
    template = _template_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, template_id=version.template_id)
    if template.is_platform_immutable and not _is_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Diffing a platform-immutable layer requires a super admin.")
    return success_response({
        "from_version": other.version_number,
        "to_version": version.version_number,
        "diff_lines": prompt_repository.diff_versions(other, version),
    })


@router.post("/{workspace_id}/prompts/versions/{version_id}/transition")
def transition_version(
    workspace_id: str,
    version_id: str,
    payload: PromptVersionTransition,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    version = _version_or_404(db, version_id=version_id)
    template = _template_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, template_id=version.template_id)
    if template.is_platform_immutable and not _is_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transitioning a platform-immutable layer's version requires a super admin.")
    try:
        version = prompt_repository.transition_version_status(
            db, version=version, new_status=payload.new_status, actor_user_id=current_user.user_id,
            organisation_id=template.organisation_id, workspace_id=template.workspace_id, reason=payload.reason,
        )
    except InvalidVersionTransition as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_response(prompt_repository.safe_version_summary(version, template=template, reveal_full_content=True))


@router.post("/{workspace_id}/prompts/versions/{version_id}/evaluate")
def evaluate_version(
    workspace_id: str,
    version_id: str,
    payload: PromptGateRunRequest,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    """Runs the evaluation-gated promotion check (spec section 6/9) for this
    candidate version - the real RAGOrchestrator, real guardrail pipeline,
    real evaluation dataset, compared against the current production
    baseline. Does not itself transition the version's status; an authorised
    reviewer still approves/rejects deliberately based on this result."""
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    _version_or_404(db, version_id=version_id)
    dataset = evaluation_repository.get_dataset(db, organisation_id=organisation_id, workspace_id=workspace_id, dataset_id=payload.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation dataset not found.")
    try:
        result = evaluate_prompt_candidate(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=payload.widget_id, dataset=dataset,
            candidate_version_id=version_id, created_by=current_user.user_id,
        )
    except PromptGateIntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return success_response({
        "passed": result.verdict.passed,
        "reasons": result.verdict.reasons,
        "candidate_run_id": result.candidate_run_id,
        "baseline_run_id": result.baseline_run_id,
    })


@router.post("/{workspace_id}/prompts/versions/{version_id}/render-preview")
def render_version_preview(
    workspace_id: str,
    version_id: str,
    db: DbSession,
    current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    """Renders this single layer's content with fixture sample values (not
    the full assembled composite - see GET .../prompts/preview for that)."""
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    version = _version_or_404(db, version_id=version_id)
    template = _template_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, template_id=version.template_id)
    if template.is_platform_immutable and not _is_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Previewing a platform-immutable layer requires a super admin.")
    schema = variables_schema_from_json(version.variables_schema_json)
    sample_variables = {spec.name: f"<sample {spec.name}>" for spec in schema}
    try:
        rendered = render_layer_content(version.content, sample_variables, schema)
    except PromptValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return success_response({"rendered": rendered, "sample_variables": sample_variables})


@router.get("/{workspace_id}/prompts/preview")
def render_composite_preview(
    workspace_id: str,
    db: DbSession,
    _current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
    widget_id: str | None = Query(default=None),
) -> dict[str, object]:
    """The full assembled system/user prompt as it would actually be sent for
    this widget right now (dormant scopes get back the same dormant
    indicator app.ai.rag_orchestrator would fall back to)."""
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        composite = resolve_composite_prompt(
            db, prompt_key="grounded_rag_answer", organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id,
            question="<sample question>", context="[1] Sample Source | Sample retrieved evidence text.", conversation_id=None,
        )
    except PromptResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if composite is None:
        return success_response({"engaged": False, "system_prompt": None, "user_prompt": None})
    return success_response({
        "engaged": True,
        "version": composite.rendered.version,
        "system_prompt": composite.rendered.system_prompt,
        "user_prompt": composite.rendered.user_prompt,
        "resolved_layer_version_ids": composite.resolved_layer_version_ids,
        "experiment_id": composite.experiment_id,
        "experiment_arm": composite.experiment_arm,
    })


# --- deployments ----------------------------------------------------------


@router.get("/{workspace_id}/prompts/deployments")
def get_deployment(
    workspace_id: str,
    db: DbSession,
    _current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
    layer: str = Query(...),
    widget_id: str | None = Query(default=None),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    scope_org = None if layer == LAYER_PLATFORM_CORE else organisation_id
    scope_ws = None if layer == LAYER_PLATFORM_CORE else workspace_id
    deployment = prompt_repository.get_active_deployment(db, layer=layer, organisation_id=scope_org, workspace_id=scope_ws, widget_id=widget_id)
    if deployment is None:
        return success_response(None)
    return success_response(_deployment_dict(deployment))


@router.post("/{workspace_id}/prompts/deployments", status_code=status.HTTP_201_CREATED)
def deploy_version(
    workspace_id: str,
    payload: PromptDeploymentCreate,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    version = _version_or_404(db, version_id=payload.version_id)
    template = _template_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, template_id=version.template_id)
    if template.is_platform_immutable and not _is_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Deploying a platform-immutable layer requires a super admin.")
    scope_org = None if template.is_platform_immutable else organisation_id
    scope_ws = None if template.is_platform_immutable else workspace_id
    scope_widget = None if template.is_platform_immutable else payload.widget_id
    try:
        deployment = prompt_repository.deploy_version(
            db, version=version, template=template, organisation_id=scope_org, workspace_id=scope_ws, widget_id=scope_widget,
            actor_user_id=current_user.user_id, rollout_percentage=payload.rollout_percentage,
        )
    except (LayerScopeMismatch, VersionNotApproved) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_response(_deployment_dict(deployment))


@router.post("/{workspace_id}/prompts/deployments/{deployment_id}/rollback")
def rollback_deployment(
    workspace_id: str,
    deployment_id: str,
    payload: PromptRollbackRequest,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    deployment = prompt_repository.get_deployment(db, deployment_id=deployment_id)
    if deployment is None or (deployment.organisation_id is not None and deployment.organisation_id != organisation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt deployment not found.")
    if deployment.organisation_id is None and not _is_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rolling back a platform-immutable layer requires a super admin.")
    try:
        deployment = prompt_repository.rollback_deployment(db, deployment=deployment, actor_user_id=current_user.user_id, reason=payload.reason)
    except NoRollbackTarget as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_response(_deployment_dict(deployment))


def _deployment_dict(deployment) -> dict:
    return {
        "id": deployment.id,
        "organisation_id": deployment.organisation_id,
        "workspace_id": deployment.workspace_id,
        "widget_id": deployment.widget_id,
        "layer": deployment.layer,
        "active_version_id": deployment.active_version_id,
        "previous_version_id": deployment.previous_version_id,
        "rollout_percentage": deployment.rollout_percentage,
        "deployed_by_user_id": deployment.deployed_by_user_id,
        "created_at": deployment.created_at.isoformat() if deployment.created_at else None,
        "updated_at": deployment.updated_at.isoformat() if deployment.updated_at else None,
    }


# --- experiments ------------------------------------------------------------


@router.get("/{workspace_id}/prompts/experiments")
def list_experiments(
    workspace_id: str,
    db: DbSession,
    _current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
    widget_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    experiments = [e for e in prompt_repository.list_experiments_for_widget(db, widget_id=widget_id) if e.organisation_id == organisation_id]
    return success_response([PromptExperimentRead.model_validate(e).model_dump(mode="json") for e in experiments])


@router.post("/{workspace_id}/prompts/experiments", status_code=status.HTTP_201_CREATED)
def create_experiment(
    workspace_id: str,
    payload: PromptExperimentCreate,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        experiment = prompt_repository.create_experiment(
            db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=payload.widget_id, layer=payload.layer,
            control_version_id=payload.control_version_id, candidate_version_id=payload.candidate_version_id,
            traffic_allocation_percentage=payload.traffic_allocation_percentage, created_by_user_id=current_user.user_id,
            is_super_admin=_is_super_admin(current_user), success_criteria=payload.success_criteria,
            evaluation_dataset_id=payload.evaluation_dataset_id, max_duration_hours=payload.max_duration_hours,
        )
    except PlatformLayerRequiresSuperAdmin as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return success_response(PromptExperimentRead.model_validate(experiment).model_dump(mode="json"))


@router.post("/{workspace_id}/prompts/experiments/{experiment_id}/start")
def start_experiment(
    workspace_id: str,
    experiment_id: str,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    experiment = _experiment_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, experiment_id=experiment_id)
    try:
        experiment = prompt_repository.start_experiment(db, experiment=experiment, actor_user_id=current_user.user_id, is_super_admin=_is_super_admin(current_user))
    except (PlatformLayerRequiresSuperAdmin, ExperimentNotGated) as exc:
        status_code = status.HTTP_403_FORBIDDEN if isinstance(exc, PlatformLayerRequiresSuperAdmin) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return success_response(PromptExperimentRead.model_validate(experiment).model_dump(mode="json"))


@router.post("/{workspace_id}/prompts/experiments/{experiment_id}/kill")
def kill_experiment(
    workspace_id: str,
    experiment_id: str,
    payload: PromptExperimentKill,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    experiment = _experiment_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, experiment_id=experiment_id)
    experiment = prompt_repository.kill_experiment(db, experiment=experiment, actor_user_id=current_user.user_id, reason=payload.reason)
    return success_response(PromptExperimentRead.model_validate(experiment).model_dump(mode="json"))


@router.post("/{workspace_id}/prompts/experiments/{experiment_id}/complete")
def complete_experiment(
    workspace_id: str,
    experiment_id: str,
    db: DbSession,
    current_user: PromptManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    experiment = _experiment_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, experiment_id=experiment_id)
    experiment = prompt_repository.complete_experiment(db, experiment=experiment, actor_user_id=current_user.user_id)
    return success_response(PromptExperimentRead.model_validate(experiment).model_dump(mode="json"))


@router.get("/{workspace_id}/prompts/experiments/{experiment_id}/metrics")
def get_experiment_metrics(
    workspace_id: str,
    experiment_id: str,
    db: DbSession,
    _current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    experiment = _experiment_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, experiment_id=experiment_id)
    arm_metrics = compute_experiment_metrics(db, experiment_id=experiment.id)
    return success_response({
        "experiment_id": experiment.id,
        "arms": [m.__dict__ for m in arm_metrics],
        "directional_only": True,
    })


def _experiment_or_404(db: DbSession, *, organisation_id: str, workspace_id: str, experiment_id: str):
    experiment = prompt_repository.get_experiment(db, experiment_id=experiment_id)
    if experiment is None or experiment.organisation_id != organisation_id or experiment.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt experiment not found.")
    return experiment


# --- audit trail --------------------------------------------------------------


@router.get("/{workspace_id}/prompts/audit-events")
def list_audit_events(
    workspace_id: str,
    db: DbSession,
    _current_user: PromptReaderDependency,
    organisation_id: str = Query(...),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, object]:
    _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    events = prompt_repository.list_audit_events(
        db, organisation_id=organisation_id, workspace_id=workspace_id, entity_type=entity_type, entity_id=entity_id, limit=limit,
    )
    return success_response([PromptAuditEventRead.model_validate(e).model_dump(mode="json") for e in events])
