from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A production failure signal awaiting human triage before it can become
    an EvaluationCase. Never stores raw production content - question/response
    text is always passed through app.observability.redaction.redact_free_text
    before being written here (see app.evaluation.feedback.detector)."""

    __tablename__ = "evaluation_candidates"
    __table_args__ = (
        Index("ix_evaluation_candidates_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_evaluation_candidates_assistant_status", "organisation_id", "workspace_id", "widget_id", "triage_status"),
        Index("ix_evaluation_candidates_dedup_hash", "organisation_id", "workspace_id", "dedup_hash"),
        Index("ix_evaluation_candidates_signal_type", "organisation_id", "workspace_id", "signal_type"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    widget_id: Mapped[str] = mapped_column(String(36), ForeignKey("widgets.id"), nullable=False, index=True)

    source_trace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_traces.id"), nullable=True, index=True)
    source_conversation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=True, index=True)
    source_message_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chat_messages.id"), nullable=True, index=True)

    signal_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", server_default="medium")

    redacted_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    redacted_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    redaction_version: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_refs_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expected_behaviour_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    triage_status: Mapped[str] = mapped_column(String(20), nullable=False, default="new", server_default="new")
    root_cause_category: Mapped[str | None] = mapped_column(String(60), nullable=True)

    expected_document_ids_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expected_source_labels_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expected_answerability: Mapped[str | None] = mapped_column(String(40), nullable=True)
    triage_details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    reviewer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    duplicate_of_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation_candidates.id"), nullable=True, index=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_reopen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    dataset_destination_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation_datasets.id"), nullable=True, index=True)
    promoted_case_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation_cases.id"), nullable=True, index=True)

    first_triaged_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class EvaluationDatasetVersionEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only changelog of dataset version bumps. Never mutated after
    creation - historical EvaluationRun rows already snapshot the dataset
    version they ran against, so this table only needs to explain *why* the
    version moved, not rewrite the past."""

    __tablename__ = "evaluation_dataset_version_events"
    __table_args__ = (
        Index("ix_evaluation_dataset_version_events_dataset", "dataset_id", "created_at"),
        Index("ix_evaluation_dataset_version_events_tenant_workspace", "organisation_id", "workspace_id"),
    )

    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_datasets.id"), nullable=False, index=True)
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    from_version: Mapped[str] = mapped_column(String(40), nullable=False)
    to_version: Mapped[str] = mapped_column(String(40), nullable=False)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_cases.id"), nullable=False, index=True)
    candidate_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation_candidates.id"), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    changelog_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvaluationRegressionReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stored output of comparing one evaluation run against a baseline run -
    persisted (rather than only printed by the CLI) so the dashboard's
    Regression Reports section can list/inspect past comparisons."""

    __tablename__ = "evaluation_regression_reports"
    __table_args__ = (
        Index("ix_evaluation_regression_reports_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_evaluation_regression_reports_run", "run_id"),
        Index("ix_evaluation_regression_reports_dataset", "dataset_id", "created_at"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    widget_id: Mapped[str] = mapped_column(String(36), ForeignKey("widgets.id"), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_datasets.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    baseline_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation_runs.id"), nullable=True, index=True)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    verdict_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    verdict_reasons_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
