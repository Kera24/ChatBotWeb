import { dashboardApiGet, dashboardApiPatch, dashboardApiPost } from "./client";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type TriageStatus = "new" | "triaged" | "needs_information" | "accepted" | "rejected" | "duplicate" | "resolved";
export type CandidateSeverity = "low" | "medium" | "high" | "critical";

export type EvaluationCandidate = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  widget_id: string;
  source_trace_id: string | null;
  source_conversation_id: string | null;
  source_message_id: string | null;
  signal_type: string;
  severity: CandidateSeverity | string;
  redacted_question: string | null;
  redacted_response: string | null;
  redaction_version: string;
  evidence_refs_json: Array<{ document_id: string | null; chunk_id: string | null; source_title: string | null }> | null;
  expected_behaviour_note: string | null;
  triage_status: TriageStatus | string;
  root_cause_category: string | null;
  expected_document_ids_json: string[] | null;
  expected_source_labels_json: string[] | null;
  expected_answerability: string | null;
  triage_details_json: Record<string, unknown> | null;
  reviewer_id: string | null;
  notes: string | null;
  dedup_hash: string;
  duplicate_of_id: string | null;
  occurrence_count: number;
  is_reopen: boolean;
  dataset_destination_id: string | null;
  promoted_case_id: string | null;
  first_triaged_at: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DuplicateSuggestion = {
  candidate_id: string;
  match_reason: string;
  similarity: number;
  redacted_question: string | null;
  triage_status: string;
};

export type EvaluationCandidateDetail = {
  candidate: EvaluationCandidate;
  potential_duplicates: DuplicateSuggestion[];
  source_trace_public_id: string | null;
};

export type EvaluationDatasetVersionEvent = {
  id: string;
  dataset_id: string;
  from_version: string;
  to_version: string;
  case_id: string;
  candidate_id: string | null;
  created_by: string | null;
  changelog_note: string | null;
  created_at: string;
};

export type EvaluationRegressionReport = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  widget_id: string;
  dataset_id: string;
  run_id: string;
  baseline_run_id: string | null;
  report_json: Record<string, unknown>;
  verdict_passed: boolean;
  verdict_reasons_json: string[] | null;
  created_by: string | null;
  created_at: string;
};

export type FeedbackLoopMetrics = {
  candidates_by_status: Record<string, number>;
  candidates_by_signal_type: Record<string, number>;
  candidates_by_severity: Record<string, number>;
  failures_by_root_cause: Record<string, number>;
  avg_time_to_triage_hours: number | null;
  avg_time_to_resolution_hours: number | null;
  cases_added_per_dataset_version: Record<string, number>;
  recurrence_rate: number;
  reopen_rate: number;
  regression_escape_rate: number | null;
  fixed_case_confirmation_rate: number | null;
};

export type CandidateListMeta = { limit: number; offset: number; count: number; total: number };

export type CandidateListParams = {
  widgetId?: string;
  triage_status?: string;
  signal_type?: string;
  severity?: string;
  root_cause_category?: string;
  limit?: number;
  offset?: number;
};

function workspacePath(session: DevelopmentDashboardSession, suffix: string) {
  return `/api/v1/workspaces/${session.workspaceId}${suffix}`;
}

function tenantParams(session: DevelopmentDashboardSession) {
  return { organisation_id: session.organisationId };
}

export function listEvaluationCandidates(session: DevelopmentDashboardSession, params: CandidateListParams = {}) {
  return dashboardApiGet<EvaluationCandidate[], CandidateListMeta>({
    path: workspacePath(session, "/evaluation-candidates"),
    session,
    searchParams: {
      ...tenantParams(session),
      widget_id: params.widgetId,
      triage_status: params.triage_status,
      signal_type: params.signal_type,
      severity: params.severity,
      root_cause_category: params.root_cause_category,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    },
  });
}

export function getEvaluationCandidate(session: DevelopmentDashboardSession, candidateId: string) {
  return dashboardApiGet<EvaluationCandidateDetail>({
    path: workspacePath(session, `/evaluation-candidates/${candidateId}`),
    session,
    searchParams: tenantParams(session),
  });
}

export function getFeedbackLoopMetrics(session: DevelopmentDashboardSession, widgetId?: string) {
  return dashboardApiGet<FeedbackLoopMetrics>({
    path: workspacePath(session, "/evaluation-candidates/metrics"),
    session,
    searchParams: { ...tenantParams(session), widget_id: widgetId },
  });
}

export type CreateCandidatePayload = {
  widget_id: string;
  signal_type: string;
  severity?: string;
  question: string;
  response?: string | null;
  reason_code?: string;
  source_trace_id?: string | null;
  source_conversation_id?: string | null;
  source_message_id?: string | null;
  notes?: string | null;
};

export function createEvaluationCandidate(session: DevelopmentDashboardSession, payload: CreateCandidatePayload) {
  return dashboardApiPost<EvaluationCandidate>({
    path: workspacePath(session, "/evaluation-candidates"),
    session,
    searchParams: tenantParams(session),
    body: payload,
  });
}

export type TriageUpdatePayload = {
  triage_status?: string;
  severity?: string;
  root_cause_category?: string;
  expected_document_ids?: string[];
  expected_source_labels?: string[];
  expected_answerability?: string;
  triage_details?: Record<string, unknown>;
  expected_behaviour_note?: string;
  notes?: string;
};

export function updateCandidateTriage(session: DevelopmentDashboardSession, candidateId: string, payload: TriageUpdatePayload) {
  return dashboardApiPatch<EvaluationCandidate>({
    path: workspacePath(session, `/evaluation-candidates/${candidateId}`),
    session,
    searchParams: tenantParams(session),
    body: payload,
  });
}

export function markCandidateDuplicate(session: DevelopmentDashboardSession, candidateId: string, duplicateOfId: string) {
  return dashboardApiPost<EvaluationCandidate>({
    path: workspacePath(session, `/evaluation-candidates/${candidateId}/mark-duplicate`),
    session,
    searchParams: tenantParams(session),
    body: { duplicate_of_id: duplicateOfId },
  });
}

export type PromoteCandidateResult = { candidate: EvaluationCandidate; case_id: string; dataset_version_event: EvaluationDatasetVersionEvent };

export function promoteCandidate(session: DevelopmentDashboardSession, candidateId: string, datasetId: string, changelogNote?: string) {
  return dashboardApiPost<PromoteCandidateResult>({
    path: workspacePath(session, `/evaluation-candidates/${candidateId}/promote`),
    session,
    searchParams: tenantParams(session),
    body: { dataset_id: datasetId, changelog_note: changelogNote ?? null },
  });
}

export function listDatasetVersionEvents(session: DevelopmentDashboardSession, datasetId?: string) {
  return dashboardApiGet<EvaluationDatasetVersionEvent[]>({
    path: workspacePath(session, "/evaluation-dataset-versions"),
    session,
    searchParams: { ...tenantParams(session), dataset_id: datasetId },
  });
}

export function listRegressionReports(session: DevelopmentDashboardSession, datasetId?: string) {
  return dashboardApiGet<EvaluationRegressionReport[]>({
    path: workspacePath(session, "/evaluation-regression-reports"),
    session,
    searchParams: { ...tenantParams(session), dataset_id: datasetId },
  });
}

export function getRegressionReport(session: DevelopmentDashboardSession, reportId: string) {
  return dashboardApiGet<EvaluationRegressionReport>({
    path: workspacePath(session, `/evaluation-regression-reports/${reportId}`),
    session,
    searchParams: tenantParams(session),
  });
}
