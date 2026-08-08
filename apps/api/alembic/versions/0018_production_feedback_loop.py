"""add production-to-evaluation feedback loop tables

Revision ID: 0018_production_feedback_loop
Revises: 0017_ai_observability
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0018_production_feedback_loop"
down_revision: str | None = "0017_ai_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.create_table(
        "evaluation_candidates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("widget_id", sa.String(length=36), nullable=False),
        sa.Column("source_trace_id", sa.String(length=36), nullable=True),
        sa.Column("source_conversation_id", sa.String(length=36), nullable=True),
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
        sa.Column("signal_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("redacted_question", sa.Text(), nullable=True),
        sa.Column("redacted_response", sa.Text(), nullable=True),
        sa.Column("redaction_version", sa.String(length=20), nullable=False),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=True),
        sa.Column("expected_behaviour_note", sa.Text(), nullable=True),
        sa.Column("triage_status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("root_cause_category", sa.String(length=60), nullable=True),
        sa.Column("expected_document_ids_json", sa.JSON(), nullable=True),
        sa.Column("expected_source_labels_json", sa.JSON(), nullable=True),
        sa.Column("expected_answerability", sa.String(length=40), nullable=True),
        sa.Column("triage_details_json", sa.JSON(), nullable=True),
        sa.Column("reviewer_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("dedup_hash", sa.String(length=64), nullable=False),
        sa.Column("duplicate_of_id", sa.String(length=36), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_reopen", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("dataset_destination_id", sa.String(length=36), nullable=True),
        sa.Column("promoted_case_id", sa.String(length=36), nullable=True),
        sa.Column("first_triaged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_candidates_organisation_id", "evaluation_candidates", ["organisation_id"])
    op.create_index("ix_evaluation_candidates_workspace_id", "evaluation_candidates", ["workspace_id"])
    op.create_index("ix_evaluation_candidates_widget_id", "evaluation_candidates", ["widget_id"])
    op.create_index("ix_evaluation_candidates_source_trace_id", "evaluation_candidates", ["source_trace_id"])
    op.create_index("ix_evaluation_candidates_source_conversation_id", "evaluation_candidates", ["source_conversation_id"])
    op.create_index("ix_evaluation_candidates_source_message_id", "evaluation_candidates", ["source_message_id"])
    op.create_index("ix_evaluation_candidates_reviewer_id", "evaluation_candidates", ["reviewer_id"])
    op.create_index("ix_evaluation_candidates_duplicate_of_id", "evaluation_candidates", ["duplicate_of_id"])
    op.create_index("ix_evaluation_candidates_dataset_destination_id", "evaluation_candidates", ["dataset_destination_id"])
    op.create_index("ix_evaluation_candidates_promoted_case_id", "evaluation_candidates", ["promoted_case_id"])
    op.create_index("ix_evaluation_candidates_tenant_workspace", "evaluation_candidates", ["organisation_id", "workspace_id"])
    op.create_index(
        "ix_evaluation_candidates_assistant_status",
        "evaluation_candidates",
        ["organisation_id", "workspace_id", "widget_id", "triage_status"],
    )
    op.create_index("ix_evaluation_candidates_dedup_hash", "evaluation_candidates", ["organisation_id", "workspace_id", "dedup_hash"])
    op.create_index("ix_evaluation_candidates_signal_type", "evaluation_candidates", ["organisation_id", "workspace_id", "signal_type"])

    op.create_table(
        "evaluation_dataset_version_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("from_version", sa.String(length=40), nullable=False),
        sa.Column("to_version", sa.String(length=40), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("changelog_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_dataset_version_events_dataset_id", "evaluation_dataset_version_events", ["dataset_id"])
    op.create_index("ix_evaluation_dataset_version_events_organisation_id", "evaluation_dataset_version_events", ["organisation_id"])
    op.create_index("ix_evaluation_dataset_version_events_workspace_id", "evaluation_dataset_version_events", ["workspace_id"])
    op.create_index("ix_evaluation_dataset_version_events_case_id", "evaluation_dataset_version_events", ["case_id"])
    op.create_index("ix_evaluation_dataset_version_events_candidate_id", "evaluation_dataset_version_events", ["candidate_id"])
    op.create_index(
        "ix_evaluation_dataset_version_events_dataset",
        "evaluation_dataset_version_events",
        ["dataset_id", "created_at"],
    )
    op.create_index(
        "ix_evaluation_dataset_version_events_tenant_workspace",
        "evaluation_dataset_version_events",
        ["organisation_id", "workspace_id"],
    )

    op.create_table(
        "evaluation_regression_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("widget_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("baseline_run_id", sa.String(length=36), nullable=True),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("verdict_passed", sa.Boolean(), nullable=False),
        sa.Column("verdict_reasons_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_regression_reports_organisation_id", "evaluation_regression_reports", ["organisation_id"])
    op.create_index("ix_evaluation_regression_reports_workspace_id", "evaluation_regression_reports", ["workspace_id"])
    op.create_index("ix_evaluation_regression_reports_widget_id", "evaluation_regression_reports", ["widget_id"])
    op.create_index("ix_evaluation_regression_reports_dataset_id", "evaluation_regression_reports", ["dataset_id"])
    op.create_index("ix_evaluation_regression_reports_run_id", "evaluation_regression_reports", ["run_id"])
    op.create_index("ix_evaluation_regression_reports_baseline_run_id", "evaluation_regression_reports", ["baseline_run_id"])
    op.create_index(
        "ix_evaluation_regression_reports_tenant_workspace",
        "evaluation_regression_reports",
        ["organisation_id", "workspace_id"],
    )
    op.create_index("ix_evaluation_regression_reports_run", "evaluation_regression_reports", ["run_id"])
    op.create_index("ix_evaluation_regression_reports_dataset", "evaluation_regression_reports", ["dataset_id", "created_at"])

    op.add_column("evaluation_runs", sa.Column("trigger_source", sa.String(length=20), nullable=True))
    op.add_column("evaluation_cases", sa.Column("source_candidate_id", sa.String(length=36), nullable=True))
    op.create_index("ix_evaluation_cases_source_candidate_id", "evaluation_cases", ["source_candidate_id"])

    if dialect != "sqlite":
        op.create_foreign_key(
            "fk_evaluation_candidates_organisation_id_organisations", "evaluation_candidates", "organisations", ["organisation_id"], ["id"]
        )
        op.create_foreign_key("fk_evaluation_candidates_workspace_id_workspaces", "evaluation_candidates", "workspaces", ["workspace_id"], ["id"])
        op.create_foreign_key("fk_evaluation_candidates_widget_id_widgets", "evaluation_candidates", "widgets", ["widget_id"], ["id"])
        op.create_foreign_key("fk_evaluation_candidates_source_trace_id_ai_traces", "evaluation_candidates", "ai_traces", ["source_trace_id"], ["id"])
        op.create_foreign_key(
            "fk_evaluation_candidates_source_conversation_id_chat_sessions",
            "evaluation_candidates",
            "chat_sessions",
            ["source_conversation_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_candidates_source_message_id_chat_messages", "evaluation_candidates", "chat_messages", ["source_message_id"], ["id"]
        )
        op.create_foreign_key("fk_evaluation_candidates_reviewer_id_users", "evaluation_candidates", "users", ["reviewer_id"], ["id"])
        op.create_foreign_key(
            "fk_evaluation_candidates_duplicate_of_id_evaluation_candidates",
            "evaluation_candidates",
            "evaluation_candidates",
            ["duplicate_of_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_candidates_dataset_destination_id_evaluation_datasets",
            "evaluation_candidates",
            "evaluation_datasets",
            ["dataset_destination_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_candidates_promoted_case_id_evaluation_cases", "evaluation_candidates", "evaluation_cases", ["promoted_case_id"], ["id"]
        )

        op.create_foreign_key(
            "fk_evaluation_dataset_version_events_dataset_id_evaluation_datasets",
            "evaluation_dataset_version_events",
            "evaluation_datasets",
            ["dataset_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_dataset_version_events_organisation_id_organisations",
            "evaluation_dataset_version_events",
            "organisations",
            ["organisation_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_dataset_version_events_workspace_id_workspaces",
            "evaluation_dataset_version_events",
            "workspaces",
            ["workspace_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_dataset_version_events_case_id_evaluation_cases",
            "evaluation_dataset_version_events",
            "evaluation_cases",
            ["case_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_dataset_version_events_candidate_id_evaluation_candidates",
            "evaluation_dataset_version_events",
            "evaluation_candidates",
            ["candidate_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_dataset_version_events_created_by_users", "evaluation_dataset_version_events", "users", ["created_by"], ["id"]
        )

        op.create_foreign_key(
            "fk_evaluation_regression_reports_organisation_id_organisations",
            "evaluation_regression_reports",
            "organisations",
            ["organisation_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_regression_reports_workspace_id_workspaces", "evaluation_regression_reports", "workspaces", ["workspace_id"], ["id"]
        )
        op.create_foreign_key("fk_evaluation_regression_reports_widget_id_widgets", "evaluation_regression_reports", "widgets", ["widget_id"], ["id"])
        op.create_foreign_key(
            "fk_evaluation_regression_reports_dataset_id_evaluation_datasets",
            "evaluation_regression_reports",
            "evaluation_datasets",
            ["dataset_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_evaluation_regression_reports_run_id_evaluation_runs", "evaluation_regression_reports", "evaluation_runs", ["run_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_evaluation_regression_reports_baseline_run_id_evaluation_runs",
            "evaluation_regression_reports",
            "evaluation_runs",
            ["baseline_run_id"],
            ["id"],
        )

        op.create_foreign_key(
            "fk_evaluation_cases_source_candidate_id_evaluation_candidates",
            "evaluation_cases",
            "evaluation_candidates",
            ["source_candidate_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "sqlite":
        op.drop_constraint("fk_evaluation_cases_source_candidate_id_evaluation_candidates", "evaluation_cases", type_="foreignkey")

        op.drop_constraint("fk_evaluation_regression_reports_baseline_run_id_evaluation_runs", "evaluation_regression_reports", type_="foreignkey")
        op.drop_constraint("fk_evaluation_regression_reports_run_id_evaluation_runs", "evaluation_regression_reports", type_="foreignkey")
        op.drop_constraint("fk_evaluation_regression_reports_dataset_id_evaluation_datasets", "evaluation_regression_reports", type_="foreignkey")
        op.drop_constraint("fk_evaluation_regression_reports_widget_id_widgets", "evaluation_regression_reports", type_="foreignkey")
        op.drop_constraint("fk_evaluation_regression_reports_workspace_id_workspaces", "evaluation_regression_reports", type_="foreignkey")
        op.drop_constraint("fk_evaluation_regression_reports_organisation_id_organisations", "evaluation_regression_reports", type_="foreignkey")

        op.drop_constraint("fk_evaluation_dataset_version_events_created_by_users", "evaluation_dataset_version_events", type_="foreignkey")
        op.drop_constraint(
            "fk_evaluation_dataset_version_events_candidate_id_evaluation_candidates", "evaluation_dataset_version_events", type_="foreignkey"
        )
        op.drop_constraint("fk_evaluation_dataset_version_events_case_id_evaluation_cases", "evaluation_dataset_version_events", type_="foreignkey")
        op.drop_constraint("fk_evaluation_dataset_version_events_workspace_id_workspaces", "evaluation_dataset_version_events", type_="foreignkey")
        op.drop_constraint(
            "fk_evaluation_dataset_version_events_organisation_id_organisations", "evaluation_dataset_version_events", type_="foreignkey"
        )
        op.drop_constraint(
            "fk_evaluation_dataset_version_events_dataset_id_evaluation_datasets", "evaluation_dataset_version_events", type_="foreignkey"
        )

        op.drop_constraint("fk_evaluation_candidates_promoted_case_id_evaluation_cases", "evaluation_candidates", type_="foreignkey")
        op.drop_constraint("fk_evaluation_candidates_dataset_destination_id_evaluation_datasets", "evaluation_candidates", type_="foreignkey")
        op.drop_constraint("fk_evaluation_candidates_duplicate_of_id_evaluation_candidates", "evaluation_candidates", type_="foreignkey")
        op.drop_constraint("fk_evaluation_candidates_reviewer_id_users", "evaluation_candidates", type_="foreignkey")
        op.drop_constraint("fk_evaluation_candidates_source_message_id_chat_messages", "evaluation_candidates", type_="foreignkey")
        op.drop_constraint("fk_evaluation_candidates_source_conversation_id_chat_sessions", "evaluation_candidates", type_="foreignkey")
        op.drop_constraint("fk_evaluation_candidates_source_trace_id_ai_traces", "evaluation_candidates", type_="foreignkey")
        op.drop_constraint("fk_evaluation_candidates_widget_id_widgets", "evaluation_candidates", type_="foreignkey")
        op.drop_constraint("fk_evaluation_candidates_workspace_id_workspaces", "evaluation_candidates", type_="foreignkey")
        op.drop_constraint("fk_evaluation_candidates_organisation_id_organisations", "evaluation_candidates", type_="foreignkey")

    op.drop_index("ix_evaluation_cases_source_candidate_id", table_name="evaluation_cases")
    op.drop_column("evaluation_cases", "source_candidate_id")
    op.drop_column("evaluation_runs", "trigger_source")

    op.drop_index("ix_evaluation_regression_reports_dataset", table_name="evaluation_regression_reports")
    op.drop_index("ix_evaluation_regression_reports_run", table_name="evaluation_regression_reports")
    op.drop_index("ix_evaluation_regression_reports_tenant_workspace", table_name="evaluation_regression_reports")
    op.drop_index("ix_evaluation_regression_reports_baseline_run_id", table_name="evaluation_regression_reports")
    op.drop_index("ix_evaluation_regression_reports_run_id", table_name="evaluation_regression_reports")
    op.drop_index("ix_evaluation_regression_reports_dataset_id", table_name="evaluation_regression_reports")
    op.drop_index("ix_evaluation_regression_reports_widget_id", table_name="evaluation_regression_reports")
    op.drop_index("ix_evaluation_regression_reports_workspace_id", table_name="evaluation_regression_reports")
    op.drop_index("ix_evaluation_regression_reports_organisation_id", table_name="evaluation_regression_reports")
    op.drop_table("evaluation_regression_reports")

    op.drop_index("ix_evaluation_dataset_version_events_tenant_workspace", table_name="evaluation_dataset_version_events")
    op.drop_index("ix_evaluation_dataset_version_events_dataset", table_name="evaluation_dataset_version_events")
    op.drop_index("ix_evaluation_dataset_version_events_candidate_id", table_name="evaluation_dataset_version_events")
    op.drop_index("ix_evaluation_dataset_version_events_case_id", table_name="evaluation_dataset_version_events")
    op.drop_index("ix_evaluation_dataset_version_events_workspace_id", table_name="evaluation_dataset_version_events")
    op.drop_index("ix_evaluation_dataset_version_events_organisation_id", table_name="evaluation_dataset_version_events")
    op.drop_index("ix_evaluation_dataset_version_events_dataset_id", table_name="evaluation_dataset_version_events")
    op.drop_table("evaluation_dataset_version_events")

    op.drop_index("ix_evaluation_candidates_signal_type", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_dedup_hash", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_assistant_status", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_tenant_workspace", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_promoted_case_id", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_dataset_destination_id", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_duplicate_of_id", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_reviewer_id", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_source_message_id", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_source_conversation_id", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_source_trace_id", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_widget_id", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_workspace_id", table_name="evaluation_candidates")
    op.drop_index("ix_evaluation_candidates_organisation_id", table_name="evaluation_candidates")
    op.drop_table("evaluation_candidates")
