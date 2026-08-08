from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.evaluation.categories import ANSWERABILITY_VALUES, CASE_CATEGORY_VALUES


class EvaluationDatasetCreate(BaseModel):
    widget_id: str
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    version: str = Field(default="1", min_length=1, max_length=40)


class EvaluationDatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    workspace_id: str
    widget_id: str
    name: str
    description: str | None
    version: str
    status: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class EvaluationCaseCreate(BaseModel):
    question: str = Field(min_length=1)
    reference_answer: str | None = None
    expected_document_ids: list[str] | None = None
    expected_source_labels: list[str] | None = None
    expected_answerability: str = "answerable"
    category: str
    tags: list[str] | None = None
    metadata_json: dict | None = None

    def validate_vocabulary(self) -> None:
        if self.expected_answerability not in ANSWERABILITY_VALUES:
            raise ValueError(f"expected_answerability must be one of {sorted(ANSWERABILITY_VALUES)}")
        if self.category not in CASE_CATEGORY_VALUES:
            raise ValueError(f"category must be one of {sorted(CASE_CATEGORY_VALUES)}")


class EvaluationCaseUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    reference_answer: str | None = None
    expected_document_ids: list[str] | None = None
    expected_source_labels: list[str] | None = None
    expected_answerability: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    metadata_json: dict | None = None


class EvaluationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    question: str
    reference_answer: str | None
    expected_document_ids: list[str] | None
    expected_source_labels: list[str] | None
    expected_answerability: str
    category: str
    tags: list[str] | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime


class EvaluationDatasetDetail(EvaluationDatasetRead):
    cases: list[EvaluationCaseRead]


class EvaluationRunCreate(BaseModel):
    dataset_id: str
    widget_id: str
    mode: str = "mock"


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    workspace_id: str
    widget_id: str
    dataset_id: str
    dataset_version: str
    provider_key: str | None
    model_key: str | None
    provider_model_name: str | None
    prompt_key: str | None
    prompt_version: str | None
    prompt_hash: str | None
    mode: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    hard_failure_cases: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    trigger_source: str | None = None


class EvaluationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    case_id: str
    actual_answer: str | None
    answer_state: str | None
    retrieved_document_ids: list[str] | None
    retrieved_chunk_ids: list[str] | None
    citations_json: list[dict] | None
    latency_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    retrieval_metrics_json: dict | None
    answer_metrics_json: dict | None
    judge_scores_json: dict | None
    passed: bool
    hard_failure: bool
    failure_reasons_json: list[str] | None
    error_message: str | None
    created_at: datetime
