"""add AI/RAG evaluation framework tables

Revision ID: 0016_evaluation_framework
Revises: 0015_billing_foundation
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0016_evaluation_framework"
down_revision: str | None = "0015_billing_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.create_table(
        "evaluation_datasets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("widget_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=40), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_datasets_organisation_id", "evaluation_datasets", ["organisation_id"])
    op.create_index("ix_evaluation_datasets_workspace_id", "evaluation_datasets", ["workspace_id"])
    op.create_index("ix_evaluation_datasets_widget_id", "evaluation_datasets", ["widget_id"])
    op.create_index("ix_evaluation_datasets_tenant_workspace", "evaluation_datasets", ["organisation_id", "workspace_id"])
    op.create_index("ix_evaluation_datasets_assistant", "evaluation_datasets", ["organisation_id", "workspace_id", "widget_id"])

    op.create_table(
        "evaluation_cases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=True),
        sa.Column("expected_document_ids", sa.JSON(), nullable=True),
        sa.Column("expected_source_labels", sa.JSON(), nullable=True),
        sa.Column("expected_answerability", sa.String(length=40), nullable=False, server_default="answerable"),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_cases_dataset_id", "evaluation_cases", ["dataset_id"])
    op.create_index("ix_evaluation_cases_organisation_id", "evaluation_cases", ["organisation_id"])
    op.create_index("ix_evaluation_cases_workspace_id", "evaluation_cases", ["workspace_id"])
    op.create_index("ix_evaluation_cases_dataset", "evaluation_cases", ["dataset_id"])
    op.create_index("ix_evaluation_cases_tenant_workspace", "evaluation_cases", ["organisation_id", "workspace_id"])
    op.create_index("ix_evaluation_cases_category", "evaluation_cases", ["dataset_id", "category"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("widget_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_version", sa.String(length=40), nullable=False),
        sa.Column("provider_key", sa.String(length=80), nullable=True),
        sa.Column("model_key", sa.String(length=80), nullable=True),
        sa.Column("provider_model_name", sa.String(length=120), nullable=True),
        sa.Column("prompt_key", sa.String(length=80), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("prompt_hash", sa.String(length=80), nullable=True),
        sa.Column("retrieval_settings_json", sa.JSON(), nullable=True),
        sa.Column("policy_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="mock"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hard_failure_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_runs_organisation_id", "evaluation_runs", ["organisation_id"])
    op.create_index("ix_evaluation_runs_workspace_id", "evaluation_runs", ["workspace_id"])
    op.create_index("ix_evaluation_runs_widget_id", "evaluation_runs", ["widget_id"])
    op.create_index("ix_evaluation_runs_dataset_id", "evaluation_runs", ["dataset_id"])
    op.create_index("ix_evaluation_runs_tenant_workspace", "evaluation_runs", ["organisation_id", "workspace_id"])
    op.create_index("ix_evaluation_runs_assistant", "evaluation_runs", ["organisation_id", "workspace_id", "widget_id"])
    op.create_index("ix_evaluation_runs_dataset", "evaluation_runs", ["dataset_id"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("actual_answer", sa.Text(), nullable=True),
        sa.Column("answer_state", sa.String(length=40), nullable=True),
        sa.Column("retrieved_document_ids", sa.JSON(), nullable=True),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("citations_json", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("retrieval_metrics_json", sa.JSON(), nullable=True),
        sa.Column("answer_metrics_json", sa.JSON(), nullable=True),
        sa.Column("judge_scores_json", sa.JSON(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("hard_failure", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("failure_reasons_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", "case_id", name="uq_evaluation_results_run_case"),
    )
    op.create_index("ix_evaluation_results_run_id", "evaluation_results", ["run_id"])
    op.create_index("ix_evaluation_results_case_id", "evaluation_results", ["case_id"])
    op.create_index("ix_evaluation_results_organisation_id", "evaluation_results", ["organisation_id"])
    op.create_index("ix_evaluation_results_workspace_id", "evaluation_results", ["workspace_id"])
    op.create_index("ix_evaluation_results_run", "evaluation_results", ["run_id"])
    op.create_index("ix_evaluation_results_case", "evaluation_results", ["case_id"])
    op.create_index("ix_evaluation_results_tenant_workspace", "evaluation_results", ["organisation_id", "workspace_id"])

    if dialect != "sqlite":
        op.create_foreign_key("fk_evaluation_datasets_organisation_id_organisations", "evaluation_datasets", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_evaluation_datasets_workspace_id_workspaces", "evaluation_datasets", "workspaces", ["workspace_id"], ["id"])
        op.create_foreign_key("fk_evaluation_datasets_widget_id_widgets", "evaluation_datasets", "widgets", ["widget_id"], ["id"])
        op.create_foreign_key("fk_evaluation_datasets_created_by_users", "evaluation_datasets", "users", ["created_by"], ["id"])

        op.create_foreign_key("fk_evaluation_cases_dataset_id_evaluation_datasets", "evaluation_cases", "evaluation_datasets", ["dataset_id"], ["id"])
        op.create_foreign_key("fk_evaluation_cases_organisation_id_organisations", "evaluation_cases", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_evaluation_cases_workspace_id_workspaces", "evaluation_cases", "workspaces", ["workspace_id"], ["id"])

        op.create_foreign_key("fk_evaluation_runs_organisation_id_organisations", "evaluation_runs", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_evaluation_runs_workspace_id_workspaces", "evaluation_runs", "workspaces", ["workspace_id"], ["id"])
        op.create_foreign_key("fk_evaluation_runs_widget_id_widgets", "evaluation_runs", "widgets", ["widget_id"], ["id"])
        op.create_foreign_key("fk_evaluation_runs_dataset_id_evaluation_datasets", "evaluation_runs", "evaluation_datasets", ["dataset_id"], ["id"])
        op.create_foreign_key("fk_evaluation_runs_created_by_users", "evaluation_runs", "users", ["created_by"], ["id"])

        op.create_foreign_key("fk_evaluation_results_run_id_evaluation_runs", "evaluation_results", "evaluation_runs", ["run_id"], ["id"])
        op.create_foreign_key("fk_evaluation_results_case_id_evaluation_cases", "evaluation_results", "evaluation_cases", ["case_id"], ["id"])
        op.create_foreign_key("fk_evaluation_results_organisation_id_organisations", "evaluation_results", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_evaluation_results_workspace_id_workspaces", "evaluation_results", "workspaces", ["workspace_id"], ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "sqlite":
        op.drop_constraint("fk_evaluation_results_workspace_id_workspaces", "evaluation_results", type_="foreignkey")
        op.drop_constraint("fk_evaluation_results_organisation_id_organisations", "evaluation_results", type_="foreignkey")
        op.drop_constraint("fk_evaluation_results_case_id_evaluation_cases", "evaluation_results", type_="foreignkey")
        op.drop_constraint("fk_evaluation_results_run_id_evaluation_runs", "evaluation_results", type_="foreignkey")

        op.drop_constraint("fk_evaluation_runs_created_by_users", "evaluation_runs", type_="foreignkey")
        op.drop_constraint("fk_evaluation_runs_dataset_id_evaluation_datasets", "evaluation_runs", type_="foreignkey")
        op.drop_constraint("fk_evaluation_runs_widget_id_widgets", "evaluation_runs", type_="foreignkey")
        op.drop_constraint("fk_evaluation_runs_workspace_id_workspaces", "evaluation_runs", type_="foreignkey")
        op.drop_constraint("fk_evaluation_runs_organisation_id_organisations", "evaluation_runs", type_="foreignkey")

        op.drop_constraint("fk_evaluation_cases_workspace_id_workspaces", "evaluation_cases", type_="foreignkey")
        op.drop_constraint("fk_evaluation_cases_organisation_id_organisations", "evaluation_cases", type_="foreignkey")
        op.drop_constraint("fk_evaluation_cases_dataset_id_evaluation_datasets", "evaluation_cases", type_="foreignkey")

        op.drop_constraint("fk_evaluation_datasets_created_by_users", "evaluation_datasets", type_="foreignkey")
        op.drop_constraint("fk_evaluation_datasets_widget_id_widgets", "evaluation_datasets", type_="foreignkey")
        op.drop_constraint("fk_evaluation_datasets_workspace_id_workspaces", "evaluation_datasets", type_="foreignkey")
        op.drop_constraint("fk_evaluation_datasets_organisation_id_organisations", "evaluation_datasets", type_="foreignkey")

    op.drop_index("ix_evaluation_results_tenant_workspace", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_case", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_run", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_workspace_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_organisation_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_case_id", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_run_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")

    op.drop_index("ix_evaluation_runs_dataset", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_assistant", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_tenant_workspace", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_dataset_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_widget_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_workspace_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_organisation_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")

    op.drop_index("ix_evaluation_cases_category", table_name="evaluation_cases")
    op.drop_index("ix_evaluation_cases_tenant_workspace", table_name="evaluation_cases")
    op.drop_index("ix_evaluation_cases_dataset", table_name="evaluation_cases")
    op.drop_index("ix_evaluation_cases_workspace_id", table_name="evaluation_cases")
    op.drop_index("ix_evaluation_cases_organisation_id", table_name="evaluation_cases")
    op.drop_index("ix_evaluation_cases_dataset_id", table_name="evaluation_cases")
    op.drop_table("evaluation_cases")

    op.drop_index("ix_evaluation_datasets_assistant", table_name="evaluation_datasets")
    op.drop_index("ix_evaluation_datasets_tenant_workspace", table_name="evaluation_datasets")
    op.drop_index("ix_evaluation_datasets_widget_id", table_name="evaluation_datasets")
    op.drop_index("ix_evaluation_datasets_workspace_id", table_name="evaluation_datasets")
    op.drop_index("ix_evaluation_datasets_organisation_id", table_name="evaluation_datasets")
    op.drop_table("evaluation_datasets")
