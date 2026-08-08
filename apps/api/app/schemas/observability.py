from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class AITraceSummaryRead(BaseModel):
    trace_id: str
    organisation_id: str
    workspace_id: str
    assistant_id: str | None = None
    conversation_id: str | None = None
    channel: str
    status: str
    answer_state: str | None = None
    fallback_used: bool
    total_latency_ms: int | None = None
    provider_key: str | None = None
    model_key: str | None = None
    total_tokens: int | None = None
    estimated_cost: Decimal | None = None
    cost_currency: str
    eval_run_id: str | None = None
    eval_case_id: str | None = None
    created_at: datetime


class AITraceStageRead(BaseModel):
    stage_name: str
    sequence_number: int
    status: str
    latency_ms: int | None = None
    reason_code: str | None = None
    error_class: str | None = None
    safe_counts: dict | None = None
    provider_model_config_version: str | None = None
    created_at: datetime


class AIRetrievalTraceRead(BaseModel):
    chunk_id: str | None = None
    document_id: str | None = None
    rank: int
    similarity_score: Decimal | None = None
    selected: bool
    rejection_reason: str | None = None
    source_title: str | None = None
    content_preview: str | None = None


class AIModelCallTraceRead(BaseModel):
    attempt_number: int
    provider_key: str | None = None
    model_key: str | None = None
    provider_model_name: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    prompt_hash: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_input_cost: Decimal | None = None
    estimated_output_cost: Decimal | None = None
    estimated_total_cost: Decimal | None = None
    cost_currency: str
    cost_calc_version: str | None = None
    pricing_known: bool
    latency_ms: int | None = None
    finish_reason: str | None = None
    outcome: str
    error_code: str | None = None
    raw_prompt_preview: str | None = None
    raw_response_preview: str | None = None


class AIGuardrailTraceRead(BaseModel):
    layer: str
    guardrail_name: str
    verdict: str
    blocked: bool
    reason_code: str | None = None
    safe_detail: dict | None = None


class AITraceDetailRead(BaseModel):
    summary: AITraceSummaryRead
    stages: list[AITraceStageRead]
    retrieval: list[AIRetrievalTraceRead]
    model_calls: list[AIModelCallTraceRead]
    guardrails: list[AIGuardrailTraceRead]


class AIObservabilityMetricsRead(BaseModel):
    request_volume: int
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    total_tokens: int
    total_estimated_cost: Decimal | None = None
    cost_currency: str
    unknown_cost_request_count: int
    answered_count: int
    fallback_count: int
    blocked_count: int
    failed_count: int
    fallback_rate: float
    blocked_rate: float
    provider_failure_rate: float
    citation_coverage: float | None = None
    evidence_insufficient_rate: float


class AIAnomalySignalRead(BaseModel):
    metric: str
    baseline_value: float | None = None
    current_value: float | None = None
    absolute_change: float | None = None
    relative_change_pct: float | None = None
    threshold_pct: float
    triggered: bool
    direction: str | None = None


class AIAlertEventRead(BaseModel):
    alert_key: str
    severity: str
    message: str
    metric_value: float | None = None
    threshold_value: float | None = None
    triggered_at: datetime
