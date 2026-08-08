from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.prompt import PROMPT_EXPERIMENT_STATUSES, PROMPT_LAYERS, PROMPT_VERSION_STATUSES


class PromptVariableSpecSchema(BaseModel):
    name: str
    required: bool = True
    max_length: int | None = None


class PromptTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str | None
    workspace_id: str | None
    layer: str
    name: str
    description: str | None
    is_platform_immutable: bool
    content_visibility: str


class PromptTemplateCreate(BaseModel):
    layer: str = Field(description=f"One of {sorted(PROMPT_LAYERS)}.")
    name: str = Field(min_length=1, max_length=255)


class PromptVersionRead(BaseModel):
    id: str
    template_id: str
    version_number: int
    status: str
    author_user_id: str | None
    change_notes: str | None
    parent_version_id: str | None
    approved_at: datetime | None
    approved_by_user_id: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    content_visibility: str
    content: str | None
    checksum: str | None
    variables_schema_json: list[dict] | None


class PromptVersionCreate(BaseModel):
    content: str = Field(min_length=0)
    variables_schema: list[PromptVariableSpecSchema] | None = None
    change_notes: str | None = None
    parent_version_id: str | None = None


class PromptVersionTransition(BaseModel):
    new_status: str = Field(description=f"One of {sorted(PROMPT_VERSION_STATUSES)}.")
    reason: str | None = None


class PromptVersionDiffRead(BaseModel):
    from_version: int
    to_version: int
    diff_lines: list[str]


class PromptDeploymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str | None
    workspace_id: str | None
    widget_id: str | None
    layer: str
    active_version_id: str
    previous_version_id: str | None
    rollout_percentage: int
    deployed_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class PromptDeploymentCreate(BaseModel):
    version_id: str
    widget_id: str | None = None
    rollout_percentage: int = Field(default=100, ge=0, le=100)


class PromptRollbackRequest(BaseModel):
    reason: str | None = None


class PromptExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    workspace_id: str
    widget_id: str
    layer: str
    control_version_id: str
    candidate_version_id: str
    traffic_allocation_percentage: int
    start_at: datetime | None
    end_at: datetime | None
    max_duration_hours: int | None
    status: str
    success_criteria_json: dict | None
    evaluation_dataset_id: str | None
    candidate_gate_run_id: str | None
    safety_gate_state: str
    created_by_user_id: str | None
    created_at: datetime


class PromptExperimentCreate(BaseModel):
    widget_id: str
    layer: str = Field(description=f"One of {sorted(PROMPT_LAYERS)}.")
    control_version_id: str
    candidate_version_id: str
    traffic_allocation_percentage: int = Field(default=10, ge=0, le=100)
    success_criteria: dict | None = None
    evaluation_dataset_id: str | None = None
    max_duration_hours: int | None = Field(default=None, gt=0)


class PromptExperimentKill(BaseModel):
    reason: str | None = None


class ArmMetricsRead(BaseModel):
    arm: str
    request_count: int
    fallback_count: int
    fallback_rate: float | None
    failed_count: int
    avg_latency_ms: float | None
    avg_total_tokens: float | None
    avg_estimated_cost: float | None
    sufficient_sample: bool


class PromptGateRunRequest(BaseModel):
    dataset_id: str
    widget_id: str


class PromptAuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    action: str
    actor_user_id: str | None
    organisation_id: str | None
    workspace_id: str | None
    before_json: dict | None
    after_json: dict | None
    reason: str | None
    created_at: datetime


__all__ = [
    "PROMPT_EXPERIMENT_STATUSES",
    "PROMPT_VERSION_STATUSES",
    "ArmMetricsRead",
    "PromptAuditEventRead",
    "PromptDeploymentCreate",
    "PromptDeploymentRead",
    "PromptExperimentCreate",
    "PromptExperimentKill",
    "PromptExperimentRead",
    "PromptGateRunRequest",
    "PromptRollbackRequest",
    "PromptTemplateCreate",
    "PromptTemplateRead",
    "PromptVariableSpecSchema",
    "PromptVersionCreate",
    "PromptVersionDiffRead",
    "PromptVersionRead",
    "PromptVersionTransition",
]
