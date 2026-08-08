from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Layer taxonomy (see docs/architecture/prompts.md for the full 8-layer model).
# Layers 1+2+3+8 (platform safety policy, RAG answer policy, citation/grounding
# requirements, structured output schema) are deliberately consolidated into a
# single PLATFORM_CORE template - they are always authored/approved together by
# a super admin and always evaluated as one unit, so independent versioning
# would let two immutable layers drift into an untested combination in
# production. Layers 4/5 stay independently versioned since they are
# workspace-scoped and lower blast radius. Layers 6/7 (evidence block, user
# question) are runtime-injected variable slots, never stored as templates.
LAYER_PLATFORM_CORE = "platform_core"
LAYER_ASSISTANT_PERSONA_TONE = "assistant_persona_tone"
LAYER_ORGANISATION_GUIDANCE = "organisation_guidance"
PROMPT_LAYERS = (LAYER_PLATFORM_CORE, LAYER_ASSISTANT_PERSONA_TONE, LAYER_ORGANISATION_GUIDANCE)
PLATFORM_IMMUTABLE_LAYERS = (LAYER_PLATFORM_CORE,)

PROMPT_VERSION_STATUSES = (
    "draft",
    "under_evaluation",
    "approved",
    "active",
    "superseded",
    "rolled_back",
    "rejected",
)

PROMPT_EXPERIMENT_STATUSES = ("draft", "running", "paused", "completed", "killed")
SAFETY_GATE_STATES = ("pending", "passed", "failed")


class PromptTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One versionable prompt layer. Platform-scoped rows (organisation_id and
    workspace_id both NULL) hold the immutable platform_core layer; all other
    rows are workspace-scoped and customer-editable. See
    app.repositories.prompt_repository for the NULL-scoped visibility rules -
    this is the first place in this codebase with intentionally NULL tenant
    columns, so reads never use the blanket organisation_id+workspace_id
    filter verbatim."""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        Index("ix_prompt_templates_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_prompt_templates_layer", "organisation_id", "workspace_id", "layer"),
    )

    organisation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    layer: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    is_platform_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class PromptVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One immutable version of a PromptTemplate's content. Versions are never
    edited in place - a change always creates a new row with parent_version_id
    pointing at the version it superseded. See app.prompts.render for
    variable-schema validation and checksum computation."""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        Index("ix_prompt_versions_template", "template_id", "version_number"),
        Index("ix_prompt_versions_status", "template_id", "status"),
    )

    template_id: Mapped[str] = mapped_column(String(36), ForeignKey("prompt_templates.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables_schema_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    author_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    change_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("prompt_versions.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)


class PromptDeployment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The currently-active (and previously-active, for rollback) PromptVersion
    for one layer in one scope (platform-wide, or one workspace/widget).
    Uniqueness of "one active deployment per scope+layer" is enforced in
    app.repositories.prompt_repository, not a DB constraint, because
    organisation_id/workspace_id/widget_id are intentionally NULL for
    platform-scoped rows and SQL UNIQUE treats NULLs as distinct."""

    __tablename__ = "prompt_deployments"
    __table_args__ = (
        Index("ix_prompt_deployments_scope", "organisation_id", "workspace_id", "widget_id", "layer"),
    )

    organisation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    widget_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("widgets.id"), nullable=True, index=True)
    layer: Mapped[str] = mapped_column(String(40), nullable=False)
    active_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("prompt_versions.id"), nullable=False)
    previous_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("prompt_versions.id"), nullable=True)
    rollout_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    deployed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class PromptExperiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A controlled A/B test of one layer's control vs candidate version for
    one widget's traffic. See app.prompts.experiment_assignment for the
    deterministic traffic-split logic and app.prompts.experiment_metrics for
    the per-arm metric aggregation."""

    __tablename__ = "prompt_experiments"
    __table_args__ = (
        Index("ix_prompt_experiments_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_prompt_experiments_widget_status", "widget_id", "status"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    widget_id: Mapped[str] = mapped_column(String(36), ForeignKey("widgets.id"), nullable=False, index=True)
    layer: Mapped[str] = mapped_column(String(40), nullable=False)
    control_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("prompt_versions.id"), nullable=False)
    candidate_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("prompt_versions.id"), nullable=False)
    traffic_allocation_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    start_at: Mapped[datetime | None] = mapped_column(nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(nullable=True)
    max_duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    success_criteria_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evaluation_dataset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation_datasets.id"), nullable=True)
    candidate_gate_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation_runs.id"), nullable=True)
    safety_gate_state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)


class PromptAuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only audit trail for every mutating prompt-management action
    (create/approve/reject/deploy/rollback/experiment start-or-kill). Written
    by app.repositories.prompt_repository alongside the mutation itself, never
    edited or deleted."""

    __tablename__ = "prompt_audit_events"
    __table_args__ = (
        Index("ix_prompt_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_prompt_audit_events_tenant_workspace", "organisation_id", "workspace_id"),
    )

    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    organisation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
