from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_datasets"
    __table_args__ = (
        Index("ix_evaluation_datasets_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_evaluation_datasets_assistant", "organisation_id", "workspace_id", "widget_id"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    widget_id: Mapped[str] = mapped_column(String(36), ForeignKey("widgets.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1", server_default="1")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", server_default="draft")
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    cases = relationship("EvaluationCase", back_populates="dataset", cascade="all, delete-orphan")
    runs = relationship("EvaluationRun", back_populates="dataset")


class EvaluationCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (
        Index("ix_evaluation_cases_dataset", "dataset_id"),
        Index("ix_evaluation_cases_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_evaluation_cases_category", "dataset_id", "category"),
    )

    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_datasets.id"), nullable=False, index=True)
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_document_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expected_source_labels: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expected_answerability: Mapped[str] = mapped_column(String(40), nullable=False, default="answerable", server_default="answerable")
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    dataset = relationship("EvaluationDataset", back_populates="cases")
    results = relationship("EvaluationResult", back_populates="case")


class EvaluationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        Index("ix_evaluation_runs_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_evaluation_runs_assistant", "organisation_id", "workspace_id", "widget_id"),
        Index("ix_evaluation_runs_dataset", "dataset_id"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    widget_id: Mapped[str] = mapped_column(String(36), ForeignKey("widgets.id"), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_datasets.id"), nullable=False, index=True)
    dataset_version: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    retrieval_settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="mock", server_default="mock")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    hard_failure_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    dataset = relationship("EvaluationDataset", back_populates="runs")
    results = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")


class EvaluationResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        UniqueConstraint("run_id", "case_id", name="uq_evaluation_results_run_case"),
        Index("ix_evaluation_results_run", "run_id"),
        Index("ix_evaluation_results_case", "case_id"),
        Index("ix_evaluation_results_tenant_workspace", "organisation_id", "workspace_id"),
    )

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("evaluation_cases.id"), nullable=False, index=True)
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    actual_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    retrieved_document_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    retrieved_chunk_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    citations_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrieval_metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    answer_metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    judge_scores_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    hard_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    failure_reasons_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run = relationship("EvaluationRun", back_populates="results")
    case = relationship("EvaluationCase", back_populates="results")
