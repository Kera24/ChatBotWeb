import { dashboardApiGet } from "./client";
import type { ApiEnvelope } from "./types";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type AITraceSummary = {
  trace_id: string;
  organisation_id: string;
  workspace_id: string;
  assistant_id: string | null;
  conversation_id: string | null;
  channel: string;
  status: string;
  answer_state: string | null;
  fallback_used: boolean;
  total_latency_ms: number | null;
  provider_key: string | null;
  model_key: string | null;
  total_tokens: number | null;
  estimated_cost: string | null;
  cost_currency: string;
  eval_run_id: string | null;
  eval_case_id: string | null;
  created_at: string;
};

export type AITraceStage = {
  stage_name: string;
  sequence_number: number;
  status: string;
  latency_ms: number | null;
  reason_code: string | null;
  error_class: string | null;
  safe_counts: Record<string, unknown> | null;
  provider_model_config_version: string | null;
  created_at: string;
};

export type AIRetrievalTraceEntry = {
  chunk_id: string | null;
  document_id: string | null;
  rank: number;
  similarity_score: string | null;
  selected: boolean;
  rejection_reason: string | null;
  source_title: string | null;
  content_preview: string | null;
};

export type AIModelCallTrace = {
  attempt_number: number;
  provider_key: string | null;
  model_key: string | null;
  provider_model_name: string | null;
  prompt_key: string | null;
  prompt_version: string | null;
  prompt_hash: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  estimated_input_cost: string | null;
  estimated_output_cost: string | null;
  estimated_total_cost: string | null;
  cost_currency: string;
  cost_calc_version: string | null;
  pricing_known: boolean;
  latency_ms: number | null;
  finish_reason: string | null;
  outcome: string;
  error_code: string | null;
  raw_prompt_preview: string | null;
  raw_response_preview: string | null;
};

export type AIGuardrailTrace = {
  layer: string;
  guardrail_name: string;
  verdict: string;
  blocked: boolean;
  reason_code: string | null;
  safe_detail: Record<string, unknown> | null;
};

export type AITraceDetail = {
  summary: AITraceSummary;
  stages: AITraceStage[];
  retrieval: AIRetrievalTraceEntry[];
  model_calls: AIModelCallTrace[];
  guardrails: AIGuardrailTrace[];
};

export type AIObservabilityMetrics = {
  request_volume: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  total_tokens: number;
  total_estimated_cost: string | null;
  cost_currency: string;
  unknown_cost_request_count: number;
  answered_count: number;
  fallback_count: number;
  blocked_count: number;
  failed_count: number;
  fallback_rate: number;
  blocked_rate: number;
  provider_failure_rate: number;
  citation_coverage: number | null;
  evidence_insufficient_rate: number;
};

export type AIAnomalySignal = {
  metric: string;
  baseline_value: number | null;
  current_value: number | null;
  absolute_change: number | null;
  relative_change_pct: number | null;
  threshold_pct: number;
  triggered: boolean;
  direction: string | null;
};

export type AIAlertEvent = {
  alert_key: string;
  severity: string;
  message: string;
  metric_value: number | null;
  threshold_value: number | null;
  triggered_at: string;
};

export type ObservabilityFilters = {
  assistantId?: string;
  provider_key?: string;
  model_key?: string;
  answer_state?: string;
  status?: string;
  conversation_id?: string;
  guardrail_reason_code?: string;
  started_after?: string;
  started_before?: string;
};

export async function listTraces(
  session: DevelopmentDashboardSession,
  filters: ObservabilityFilters & { limit?: number; offset?: number } = {},
): Promise<ApiEnvelope<AITraceSummary[], { limit: number; offset: number; total: number }>> {
  return dashboardApiGet({
    path: `/api/v1/workspaces/${session.workspaceId}/observability/traces`,
    session,
    searchParams: {
      organisation_id: session.organisationId,
      assistant_id: filters.assistantId,
      provider_key: filters.provider_key,
      model_key: filters.model_key,
      answer_state: filters.answer_state,
      status: filters.status,
      conversation_id: filters.conversation_id,
      guardrail_reason_code: filters.guardrail_reason_code,
      started_after: filters.started_after,
      started_before: filters.started_before,
      limit: filters.limit ?? 50,
      offset: filters.offset ?? 0,
    },
  });
}

export async function getTraceDetail(
  session: DevelopmentDashboardSession,
  traceId: string,
  options: { includeContent?: boolean } = {},
): Promise<ApiEnvelope<AITraceDetail>> {
  return dashboardApiGet({
    path: `/api/v1/workspaces/${session.workspaceId}/observability/traces/${traceId}`,
    session,
    searchParams: {
      organisation_id: session.organisationId,
      include_content: options.includeContent ? "true" : undefined,
    },
  });
}

export async function loadObservabilityMetrics(
  session: DevelopmentDashboardSession,
  filters: ObservabilityFilters = {},
): Promise<ApiEnvelope<AIObservabilityMetrics>> {
  return dashboardApiGet({
    path: `/api/v1/workspaces/${session.workspaceId}/observability/metrics`,
    session,
    searchParams: {
      organisation_id: session.organisationId,
      assistant_id: filters.assistantId,
      provider_key: filters.provider_key,
      model_key: filters.model_key,
      started_after: filters.started_after,
      started_before: filters.started_before,
    },
  });
}

export async function listAnomalies(
  session: DevelopmentDashboardSession,
  filters: { assistantId?: string } = {},
): Promise<ApiEnvelope<AIAnomalySignal[]>> {
  return dashboardApiGet({
    path: `/api/v1/workspaces/${session.workspaceId}/observability/anomalies`,
    session,
    searchParams: { organisation_id: session.organisationId, assistant_id: filters.assistantId },
  });
}

export async function listAlerts(
  session: DevelopmentDashboardSession,
  filters: { assistantId?: string; windowHours?: number } = {},
): Promise<ApiEnvelope<AIAlertEvent[]>> {
  return dashboardApiGet({
    path: `/api/v1/workspaces/${session.workspaceId}/observability/alerts`,
    session,
    searchParams: { organisation_id: session.organisationId, assistant_id: filters.assistantId, window_hours: filters.windowHours },
  });
}
