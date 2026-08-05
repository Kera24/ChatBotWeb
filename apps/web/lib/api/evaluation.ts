import { dashboardApiGet } from "./client";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type EvaluationDataset = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  widget_id: string;
  name: string;
  description: string | null;
  version: string;
  status: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type EvaluationCase = {
  id: string;
  dataset_id: string;
  question: string;
  reference_answer: string | null;
  expected_document_ids: string[] | null;
  expected_source_labels: string[] | null;
  expected_answerability: string;
  category: string;
  tags: string[] | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type EvaluationDatasetDetail = EvaluationDataset & { cases: EvaluationCase[] };

export type EvaluationRun = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  widget_id: string;
  dataset_id: string;
  dataset_version: string;
  provider_key: string | null;
  model_key: string | null;
  provider_model_name: string | null;
  prompt_key: string | null;
  prompt_version: string | null;
  prompt_hash: string | null;
  mode: string;
  status: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  hard_failure_cases: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
};

export type EvaluationCategoryBreakdown = Record<string, { total: number; passed: number; failed: number; hard_failure: number }>;

export type EvaluationFailedCase = {
  case_id: string;
  question: string;
  category: string;
  passed: boolean;
  hard_failure: boolean;
  failure_reasons: string[];
  latency_ms: number | null;
};

export type EvaluationRunSummary = {
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  hard_failure_cases: number;
  pass_rate: number;
  retrieval_hit_rate: number | null;
  citation_coverage: number;
  fallback_rate_on_answerable: number | null;
  correct_fallback_rate_on_unanswerable: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  category_breakdown: EvaluationCategoryBreakdown;
  failed_case_details: EvaluationFailedCase[];
};

export type EvaluationGateVerdict = { passed: boolean; reasons: string[] };

export type EvaluationRunDetail = {
  run: EvaluationRun;
  summary: EvaluationRunSummary;
  gate: EvaluationGateVerdict;
};

export type EvaluationResult = {
  id: string;
  run_id: string;
  case_id: string;
  actual_answer: string | null;
  answer_state: string | null;
  retrieved_document_ids: string[] | null;
  retrieved_chunk_ids: string[] | null;
  citations_json: Array<Record<string, unknown>> | null;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  retrieval_metrics_json: Record<string, unknown> | null;
  answer_metrics_json: Record<string, unknown> | null;
  judge_scores_json: Record<string, unknown> | null;
  passed: boolean;
  hard_failure: boolean;
  failure_reasons_json: string[] | null;
  error_message: string | null;
  created_at: string;
};

export type EvaluationResultDetail = { result: EvaluationResult; case: EvaluationCase | null };

export type EvaluationRunComparison = {
  baseline: { run: EvaluationRun; summary: EvaluationRunSummary };
  candidate: { run: EvaluationRun; summary: EvaluationRunSummary };
  comparison: {
    baseline_pass_rate: number;
    candidate_pass_rate: number;
    pass_rate_delta: number;
    baseline_hard_failure_cases: number;
    candidate_hard_failure_cases: number;
    baseline_latency_p95_ms: number | null;
    candidate_latency_p95_ms: number | null;
    regressed: boolean;
  };
};

function workspacePath(session: DevelopmentDashboardSession, suffix: string) {
  return `/api/v1/workspaces/${session.workspaceId}${suffix}`;
}

function tenantParams(session: DevelopmentDashboardSession) {
  return { organisation_id: session.organisationId };
}

export function listEvaluationDatasets(session: DevelopmentDashboardSession) {
  return dashboardApiGet<EvaluationDataset[]>({
    path: workspacePath(session, "/evaluation/datasets"),
    session,
    searchParams: tenantParams(session),
  });
}

export function getEvaluationDataset(session: DevelopmentDashboardSession, datasetId: string) {
  return dashboardApiGet<EvaluationDatasetDetail>({
    path: workspacePath(session, `/evaluation/datasets/${datasetId}`),
    session,
    searchParams: tenantParams(session),
  });
}

export function listEvaluationRuns(session: DevelopmentDashboardSession, datasetId?: string) {
  return dashboardApiGet<EvaluationRun[]>({
    path: workspacePath(session, "/evaluation/runs"),
    session,
    searchParams: { ...tenantParams(session), ...(datasetId ? { dataset_id: datasetId } : {}) },
  });
}

export function getEvaluationRun(session: DevelopmentDashboardSession, runId: string) {
  return dashboardApiGet<EvaluationRunDetail>({
    path: workspacePath(session, `/evaluation/runs/${runId}`),
    session,
    searchParams: tenantParams(session),
  });
}

export function listEvaluationRunResults(session: DevelopmentDashboardSession, runId: string, onlyFailed?: boolean) {
  return dashboardApiGet<EvaluationResult[]>({
    path: workspacePath(session, `/evaluation/runs/${runId}/results`),
    session,
    searchParams: { ...tenantParams(session), ...(onlyFailed ? { only_failed: "true" } : {}) },
  });
}

export function getEvaluationRunResult(session: DevelopmentDashboardSession, runId: string, caseId: string) {
  return dashboardApiGet<EvaluationResultDetail>({
    path: workspacePath(session, `/evaluation/runs/${runId}/results/${caseId}`),
    session,
    searchParams: tenantParams(session),
  });
}

export function compareEvaluationRuns(session: DevelopmentDashboardSession, baselineRunId: string, candidateRunId: string) {
  return dashboardApiGet<EvaluationRunComparison>({
    path: workspacePath(session, "/evaluation/runs/compare"),
    session,
    searchParams: { ...tenantParams(session), baseline_run_id: baselineRunId, candidate_run_id: candidateRunId },
  });
}
