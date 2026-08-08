"""add versioned prompt management, deployments, experiments, audit trail

Revision ID: 0019_prompt_management
Revises: 0018_production_feedback_loop
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0019_prompt_management"
down_revision: str | None = "0018_production_feedback_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=True),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("layer", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("is_platform_immutable", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_templates_organisation_id", "prompt_templates", ["organisation_id"])
    op.create_index("ix_prompt_templates_workspace_id", "prompt_templates", ["workspace_id"])
    op.create_index("ix_prompt_templates_tenant_workspace", "prompt_templates", ["organisation_id", "workspace_id"])
    op.create_index("ix_prompt_templates_layer", "prompt_templates", ["organisation_id", "workspace_id", "layer"])

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables_schema_json", sa.JSON(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("author_user_id", sa.String(length=36), nullable=True),
        sa.Column("change_notes", sa.Text(), nullable=True),
        sa.Column("parent_version_id", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_versions_template_id", "prompt_versions", ["template_id"])
    op.create_index("ix_prompt_versions_template", "prompt_versions", ["template_id", "version_number"])
    op.create_index("ix_prompt_versions_status", "prompt_versions", ["template_id", "status"])

    op.create_table(
        "prompt_deployments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=True),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("widget_id", sa.String(length=36), nullable=True),
        sa.Column("layer", sa.String(length=40), nullable=False),
        sa.Column("active_version_id", sa.String(length=36), nullable=False),
        sa.Column("previous_version_id", sa.String(length=36), nullable=True),
        sa.Column("rollout_percentage", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("deployed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_deployments_organisation_id", "prompt_deployments", ["organisation_id"])
    op.create_index("ix_prompt_deployments_workspace_id", "prompt_deployments", ["workspace_id"])
    op.create_index("ix_prompt_deployments_widget_id", "prompt_deployments", ["widget_id"])
    op.create_index("ix_prompt_deployments_scope", "prompt_deployments", ["organisation_id", "workspace_id", "widget_id", "layer"])

    op.create_table(
        "prompt_experiments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("widget_id", sa.String(length=36), nullable=False),
        sa.Column("layer", sa.String(length=40), nullable=False),
        sa.Column("control_version_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_version_id", sa.String(length=36), nullable=False),
        sa.Column("traffic_allocation_percentage", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_duration_hours", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("success_criteria_json", sa.JSON(), nullable=True),
        sa.Column("evaluation_dataset_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_gate_run_id", sa.String(length=36), nullable=True),
        sa.Column("safety_gate_state", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_experiments_organisation_id", "prompt_experiments", ["organisation_id"])
    op.create_index("ix_prompt_experiments_workspace_id", "prompt_experiments", ["workspace_id"])
    op.create_index("ix_prompt_experiments_widget_id", "prompt_experiments", ["widget_id"])
    op.create_index("ix_prompt_experiments_tenant_workspace", "prompt_experiments", ["organisation_id", "workspace_id"])
    op.create_index("ix_prompt_experiments_widget_status", "prompt_experiments", ["widget_id", "status"])

    op.create_table(
        "prompt_audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=True),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_audit_events_entity", "prompt_audit_events", ["entity_type", "entity_id"])
    op.create_index("ix_prompt_audit_events_organisation_id", "prompt_audit_events", ["organisation_id"])
    op.create_index("ix_prompt_audit_events_workspace_id", "prompt_audit_events", ["workspace_id"])
    op.create_index("ix_prompt_audit_events_tenant_workspace", "prompt_audit_events", ["organisation_id", "workspace_id"])

    op.add_column("ai_model_call_traces", sa.Column("prompt_version_id", sa.String(length=36), nullable=True))
    op.add_column("ai_model_call_traces", sa.Column("experiment_id", sa.String(length=36), nullable=True))
    op.add_column("ai_model_call_traces", sa.Column("experiment_arm", sa.String(length=20), nullable=True))
    op.add_column("ai_model_call_traces", sa.Column("resolved_layer_version_ids", sa.JSON(), nullable=True))
    op.create_index("ix_ai_model_call_traces_prompt_version_id", "ai_model_call_traces", ["prompt_version_id"])
    op.create_index("ix_ai_model_call_traces_experiment_id", "ai_model_call_traces", ["experiment_id"])

    op.add_column("evaluation_runs", sa.Column("prompt_version_id", sa.String(length=36), nullable=True))
    op.create_index("ix_evaluation_runs_prompt_version_id", "evaluation_runs", ["prompt_version_id"])

    if dialect != "sqlite":
        op.create_foreign_key("fk_prompt_templates_organisation_id_organisations", "prompt_templates", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_prompt_templates_workspace_id_workspaces", "prompt_templates", "workspaces", ["workspace_id"], ["id"])
        op.create_foreign_key("fk_prompt_templates_owner_user_id_users", "prompt_templates", "users", ["owner_user_id"], ["id"])

        op.create_foreign_key("fk_prompt_versions_template_id_prompt_templates", "prompt_versions", "prompt_templates", ["template_id"], ["id"])
        op.create_foreign_key("fk_prompt_versions_author_user_id_users", "prompt_versions", "users", ["author_user_id"], ["id"])
        op.create_foreign_key("fk_prompt_versions_parent_version_id_prompt_versions", "prompt_versions", "prompt_versions", ["parent_version_id"], ["id"])
        op.create_foreign_key(
            "fk_prompt_versions_approved_by_user_id_users", "prompt_versions", "users", ["approved_by_user_id"], ["id"]
        )

        op.create_foreign_key(
            "fk_prompt_deployments_organisation_id_organisations", "prompt_deployments", "organisations", ["organisation_id"], ["id"]
        )
        op.create_foreign_key("fk_prompt_deployments_workspace_id_workspaces", "prompt_deployments", "workspaces", ["workspace_id"], ["id"])
        op.create_foreign_key("fk_prompt_deployments_widget_id_widgets", "prompt_deployments", "widgets", ["widget_id"], ["id"])
        op.create_foreign_key(
            "fk_prompt_deployments_active_version_id_prompt_versions", "prompt_deployments", "prompt_versions", ["active_version_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_prompt_deployments_previous_version_id_prompt_versions", "prompt_deployments", "prompt_versions", ["previous_version_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_prompt_deployments_deployed_by_user_id_users", "prompt_deployments", "users", ["deployed_by_user_id"], ["id"]
        )

        op.create_foreign_key(
            "fk_prompt_experiments_organisation_id_organisations", "prompt_experiments", "organisations", ["organisation_id"], ["id"]
        )
        op.create_foreign_key("fk_prompt_experiments_workspace_id_workspaces", "prompt_experiments", "workspaces", ["workspace_id"], ["id"])
        op.create_foreign_key("fk_prompt_experiments_widget_id_widgets", "prompt_experiments", "widgets", ["widget_id"], ["id"])
        op.create_foreign_key(
            "fk_prompt_experiments_control_version_id_prompt_versions", "prompt_experiments", "prompt_versions", ["control_version_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_prompt_experiments_candidate_version_id_prompt_versions",
            "prompt_experiments",
            "prompt_versions",
            ["candidate_version_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_prompt_experiments_evaluation_dataset_id_evaluation_datasets",
            "prompt_experiments",
            "evaluation_datasets",
            ["evaluation_dataset_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_prompt_experiments_candidate_gate_run_id_evaluation_runs",
            "prompt_experiments",
            "evaluation_runs",
            ["candidate_gate_run_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_prompt_experiments_created_by_user_id_users", "prompt_experiments", "users", ["created_by_user_id"], ["id"]
        )

        op.create_foreign_key("fk_prompt_audit_events_actor_user_id_users", "prompt_audit_events", "users", ["actor_user_id"], ["id"])
        op.create_foreign_key(
            "fk_prompt_audit_events_organisation_id_organisations", "prompt_audit_events", "organisations", ["organisation_id"], ["id"]
        )
        op.create_foreign_key("fk_prompt_audit_events_workspace_id_workspaces", "prompt_audit_events", "workspaces", ["workspace_id"], ["id"])

        op.create_foreign_key(
            "fk_ai_model_call_traces_prompt_version_id_prompt_versions",
            "ai_model_call_traces",
            "prompt_versions",
            ["prompt_version_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_ai_model_call_traces_experiment_id_prompt_experiments",
            "ai_model_call_traces",
            "prompt_experiments",
            ["experiment_id"],
            ["id"],
        )

        op.create_foreign_key(
            "fk_evaluation_runs_prompt_version_id_prompt_versions", "evaluation_runs", "prompt_versions", ["prompt_version_id"], ["id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "sqlite":
        op.drop_constraint("fk_evaluation_runs_prompt_version_id_prompt_versions", "evaluation_runs", type_="foreignkey")

        op.drop_constraint("fk_ai_model_call_traces_experiment_id_prompt_experiments", "ai_model_call_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_model_call_traces_prompt_version_id_prompt_versions", "ai_model_call_traces", type_="foreignkey")

        op.drop_constraint("fk_prompt_audit_events_workspace_id_workspaces", "prompt_audit_events", type_="foreignkey")
        op.drop_constraint("fk_prompt_audit_events_organisation_id_organisations", "prompt_audit_events", type_="foreignkey")
        op.drop_constraint("fk_prompt_audit_events_actor_user_id_users", "prompt_audit_events", type_="foreignkey")

        op.drop_constraint("fk_prompt_experiments_created_by_user_id_users", "prompt_experiments", type_="foreignkey")
        op.drop_constraint("fk_prompt_experiments_candidate_gate_run_id_evaluation_runs", "prompt_experiments", type_="foreignkey")
        op.drop_constraint("fk_prompt_experiments_evaluation_dataset_id_evaluation_datasets", "prompt_experiments", type_="foreignkey")
        op.drop_constraint("fk_prompt_experiments_candidate_version_id_prompt_versions", "prompt_experiments", type_="foreignkey")
        op.drop_constraint("fk_prompt_experiments_control_version_id_prompt_versions", "prompt_experiments", type_="foreignkey")
        op.drop_constraint("fk_prompt_experiments_widget_id_widgets", "prompt_experiments", type_="foreignkey")
        op.drop_constraint("fk_prompt_experiments_workspace_id_workspaces", "prompt_experiments", type_="foreignkey")
        op.drop_constraint("fk_prompt_experiments_organisation_id_organisations", "prompt_experiments", type_="foreignkey")

        op.drop_constraint("fk_prompt_deployments_deployed_by_user_id_users", "prompt_deployments", type_="foreignkey")
        op.drop_constraint("fk_prompt_deployments_previous_version_id_prompt_versions", "prompt_deployments", type_="foreignkey")
        op.drop_constraint("fk_prompt_deployments_active_version_id_prompt_versions", "prompt_deployments", type_="foreignkey")
        op.drop_constraint("fk_prompt_deployments_widget_id_widgets", "prompt_deployments", type_="foreignkey")
        op.drop_constraint("fk_prompt_deployments_workspace_id_workspaces", "prompt_deployments", type_="foreignkey")
        op.drop_constraint("fk_prompt_deployments_organisation_id_organisations", "prompt_deployments", type_="foreignkey")

        op.drop_constraint("fk_prompt_versions_approved_by_user_id_users", "prompt_versions", type_="foreignkey")
        op.drop_constraint("fk_prompt_versions_parent_version_id_prompt_versions", "prompt_versions", type_="foreignkey")
        op.drop_constraint("fk_prompt_versions_author_user_id_users", "prompt_versions", type_="foreignkey")
        op.drop_constraint("fk_prompt_versions_template_id_prompt_templates", "prompt_versions", type_="foreignkey")

        op.drop_constraint("fk_prompt_templates_owner_user_id_users", "prompt_templates", type_="foreignkey")
        op.drop_constraint("fk_prompt_templates_workspace_id_workspaces", "prompt_templates", type_="foreignkey")
        op.drop_constraint("fk_prompt_templates_organisation_id_organisations", "prompt_templates", type_="foreignkey")

    op.drop_index("ix_evaluation_runs_prompt_version_id", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "prompt_version_id")

    op.drop_index("ix_ai_model_call_traces_experiment_id", table_name="ai_model_call_traces")
    op.drop_index("ix_ai_model_call_traces_prompt_version_id", table_name="ai_model_call_traces")
    op.drop_column("ai_model_call_traces", "resolved_layer_version_ids")
    op.drop_column("ai_model_call_traces", "experiment_arm")
    op.drop_column("ai_model_call_traces", "experiment_id")
    op.drop_column("ai_model_call_traces", "prompt_version_id")

    op.drop_index("ix_prompt_audit_events_tenant_workspace", table_name="prompt_audit_events")
    op.drop_index("ix_prompt_audit_events_workspace_id", table_name="prompt_audit_events")
    op.drop_index("ix_prompt_audit_events_organisation_id", table_name="prompt_audit_events")
    op.drop_index("ix_prompt_audit_events_entity", table_name="prompt_audit_events")
    op.drop_table("prompt_audit_events")

    op.drop_index("ix_prompt_experiments_widget_status", table_name="prompt_experiments")
    op.drop_index("ix_prompt_experiments_tenant_workspace", table_name="prompt_experiments")
    op.drop_index("ix_prompt_experiments_widget_id", table_name="prompt_experiments")
    op.drop_index("ix_prompt_experiments_workspace_id", table_name="prompt_experiments")
    op.drop_index("ix_prompt_experiments_organisation_id", table_name="prompt_experiments")
    op.drop_table("prompt_experiments")

    op.drop_index("ix_prompt_deployments_scope", table_name="prompt_deployments")
    op.drop_index("ix_prompt_deployments_widget_id", table_name="prompt_deployments")
    op.drop_index("ix_prompt_deployments_workspace_id", table_name="prompt_deployments")
    op.drop_index("ix_prompt_deployments_organisation_id", table_name="prompt_deployments")
    op.drop_table("prompt_deployments")

    op.drop_index("ix_prompt_versions_status", table_name="prompt_versions")
    op.drop_index("ix_prompt_versions_template", table_name="prompt_versions")
    op.drop_index("ix_prompt_versions_template_id", table_name="prompt_versions")
    op.drop_table("prompt_versions")

    op.drop_index("ix_prompt_templates_layer", table_name="prompt_templates")
    op.drop_index("ix_prompt_templates_tenant_workspace", table_name="prompt_templates")
    op.drop_index("ix_prompt_templates_workspace_id", table_name="prompt_templates")
    op.drop_index("ix_prompt_templates_organisation_id", table_name="prompt_templates")
    op.drop_table("prompt_templates")


