from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.evaluation.categories import ANSWERABILITY_VALUES, CASE_CATEGORY_VALUES
from app.evaluation.feedback.signals import SEVERITY_LEVELS, SIGNAL_TYPE_VALUES, TRIAGE_STATUSES


class EvaluationCandidateCreate(BaseModel):
    """Manual candidate creation - the target of the "Create evaluation
    candidate" links from observability/review/conversation/evaluation
    pages. Question/response are raw here; the server redacts before
    persisting (see evaluation_candidate_repository.create_candidate)."""

    widget_id: str
    signal_type: str
    severity: str = "medium"
    question: str = Field(min_length=1)
    response: str | None = None
    reason_code: str = "manual"
    source_trace_id: str | None = None
    source_conversation_id: str | None = None
    source_message_id: str | None = None
    evidence_refs: list[dict] | None = None
    notes: str | None = Field(default=None, max_length=4000)

    def validate_vocabulary(self) -> None:
        if self.signal_type not in SIGNAL_TYPE_VALUES:
            raise ValueError(f"signal_type must be one of {sorted(SIGNAL_TYPE_VALUES)}")
        if self.severity not in SEVERITY_LEVELS:
            raise ValueError(f"severity must be one of {sorted(SEVERITY_LEVELS)}")


class EvaluationCandidateTriageUpdate(BaseModel):
    triage_status: str | None = None
    severity: str | None = None
    root_cause_category: str | None = None
    expected_document_ids: list[str] | None = None
    expected_source_labels: list[str] | None = None
    expected_answerability: str | None = None
    triage_details: dict | None = None
    expected_behaviour_note: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)

    def validate_vocabulary(self) -> None:
        if self.triage_status is not None and self.triage_status not in TRIAGE_STATUSES:
            raise ValueError(f"triage_status must be one of {sorted(TRIAGE_STATUSES)}")
        if self.severity is not None and self.severity not in SEVERITY_LEVELS:
            raise ValueError(f"severity must be one of {sorted(SEVERITY_LEVELS)}")
        if self.root_cause_category is not None and self.root_cause_category not in CASE_CATEGORY_VALUES:
            raise ValueError(f"root_cause_category must be one of {sorted(CASE_CATEGORY_VALUES)}")
        if self.expected_answerability is not None and self.expected_answerability not in ANSWERABILITY_VALUES:
            raise ValueError(f"expected_answerability must be one of {sorted(ANSWERABILITY_VALUES)}")


class EvaluationCandidateMarkDuplicate(BaseModel):
    duplicate_of_id: str


class EvaluationCandidatePromote(BaseModel):
    dataset_id: str
    changelog_note: str | None = Field(default=None, max_length=2000)


class DuplicateSuggestionRead(BaseModel):
    candidate_id: str
    match_reason: str
    similarity: float
    redacted_question: str | None
    triage_status: str


class EvaluationCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    workspace_id: str
    widget_id: str
    source_trace_id: str | None
    source_conversation_id: str | None
    source_message_id: str | None
    signal_type: str
    severity: str
    redacted_question: str | None
    redacted_response: str | None
    redaction_version: str
    evidence_refs_json: list[dict] | None
    expected_behaviour_note: str | None
    triage_status: str
    root_cause_category: str | None
    expected_document_ids_json: list[str] | None
    expected_source_labels_json: list[str] | None
    expected_answerability: str | None
    triage_details_json: dict | None
    reviewer_id: str | None
    notes: str | None
    dedup_hash: str
    duplicate_of_id: str | None
    occurrence_count: int
    is_reopen: bool
    dataset_destination_id: str | None
    promoted_case_id: str | None
    first_triaged_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EvaluationCandidateDetailRead(BaseModel):
    candidate: EvaluationCandidateRead
    potential_duplicates: list[DuplicateSuggestionRead] = []
    # candidate.source_trace_id is the internal AITrace.id (FK target); the
    # observability UI routes on AITrace.trace_id (the public correlation
    # string), so it is resolved and included here for linking purposes only.
    source_trace_public_id: str | None = None


class EvaluationDatasetVersionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    from_version: str
    to_version: str
    case_id: str
    candidate_id: str | None
    created_by: str | None
    changelog_note: str | None
    created_at: datetime


class EvaluationRegressionReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    workspace_id: str
    widget_id: str
    dataset_id: str
    run_id: str
    baseline_run_id: str | None
    report_json: dict
    verdict_passed: bool
    verdict_reasons_json: list[str] | None
    created_by: str | None
    created_at: datetime


class FeedbackLoopMetricsRead(BaseModel):
    candidates_by_status: dict[str, int]
    candidates_by_signal_type: dict[str, int]
    candidates_by_severity: dict[str, int]
    failures_by_root_cause: dict[str, int]
    avg_time_to_triage_hours: float | None
    avg_time_to_resolution_hours: float | None
    cases_added_per_dataset_version: dict[str, int]
    recurrence_rate: float
    reopen_rate: float
    regression_escape_rate: float | None
    fixed_case_confirmation_rate: float | None
