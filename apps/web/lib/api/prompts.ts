import { dashboardApiGet, dashboardApiPost } from "./client";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export const PROMPT_LAYERS = ["platform_core", "assistant_persona_tone", "organisation_guidance"] as const;
export type PromptLayer = (typeof PROMPT_LAYERS)[number];

export const CUSTOMER_EDITABLE_LAYERS: PromptLayer[] = ["assistant_persona_tone", "organisation_guidance"];

export type PromptTemplate = {
  id: string;
  organisation_id: string | null;
  workspace_id: string | null;
  layer: string;
  name: string;
  description: string | null;
  is_platform_immutable: boolean;
  content_visibility: "full" | "summary_only";
};

export type PromptVersion = {
  id: string;
  template_id: string;
  version_number: number;
  status: string;
  author_user_id: string | null;
  change_notes: string | null;
  parent_version_id: string | null;
  approved_at: string | null;
  approved_by_user_id: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  content_visibility: "full" | "summary_only";
  content: string | null;
  checksum: string | null;
  variables_schema_json: Array<{ name: string; required: boolean; max_length: number | null }> | null;
};

export type PromptDeployment = {
  id: string;
  organisation_id: string | null;
  workspace_id: string | null;
  widget_id: string | null;
  layer: string;
  active_version_id: string;
  previous_version_id: string | null;
  rollout_percentage: number;
  deployed_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type PromptExperiment = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  widget_id: string;
  layer: string;
  control_version_id: string;
  candidate_version_id: string;
  traffic_allocation_percentage: number;
  start_at: string | null;
  end_at: string | null;
  max_duration_hours: number | null;
  status: string;
  success_criteria_json: Record<string, unknown> | null;
  evaluation_dataset_id: string | null;
  candidate_gate_run_id: string | null;
  safety_gate_state: string;
  created_by_user_id: string | null;
  created_at: string;
};

export type ArmMetrics = {
  arm: string;
  request_count: number;
  fallback_count: number;
  fallback_rate: number | null;
  failed_count: number;
  avg_latency_ms: number | null;
  avg_total_tokens: number | null;
  avg_estimated_cost: number | null;
  sufficient_sample: boolean;
};

export type ExperimentMetrics = { experiment_id: string; arms: ArmMetrics[]; directional_only: boolean };

export type PromptAuditEvent = {
  id: string;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_user_id: string | null;
  organisation_id: string | null;
  workspace_id: string | null;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
  reason: string | null;
  created_at: string;
};

export type PromptGateVerdict = { passed: boolean; reasons: string[]; candidate_run_id: string; baseline_run_id: string | null };

export type PromptCompositePreview = {
  engaged: boolean;
  version?: string;
  system_prompt: string | null;
  user_prompt: string | null;
  resolved_layer_version_ids?: Record<string, string>;
  experiment_id?: string | null;
  experiment_arm?: string | null;
};

function workspacePath(session: DevelopmentDashboardSession, suffix: string) {
  return `/api/v1/workspaces/${session.workspaceId}${suffix}`;
}

function tenantParams(session: DevelopmentDashboardSession) {
  return { organisation_id: session.organisationId };
}

export function listPromptTemplates(session: DevelopmentDashboardSession) {
  return dashboardApiGet<PromptTemplate[]>({ path: workspacePath(session, "/prompts/templates"), session, searchParams: tenantParams(session) });
}

export function createPromptTemplate(session: DevelopmentDashboardSession, layer: PromptLayer, name: string) {
  return dashboardApiPost<PromptTemplate>({
    path: workspacePath(session, "/prompts/templates"),
    session,
    searchParams: tenantParams(session),
    body: { layer, name },
  });
}

export function getPromptTemplate(session: DevelopmentDashboardSession, templateId: string) {
  return dashboardApiGet<PromptTemplate>({ path: workspacePath(session, `/prompts/templates/${templateId}`), session, searchParams: tenantParams(session) });
}

export function listPromptVersions(session: DevelopmentDashboardSession, templateId: string) {
  return dashboardApiGet<PromptVersion[]>({ path: workspacePath(session, `/prompts/templates/${templateId}/versions`), session, searchParams: tenantParams(session) });
}

export function createPromptVersion(
  session: DevelopmentDashboardSession,
  templateId: string,
  payload: { content: string; change_notes?: string; parent_version_id?: string },
) {
  return dashboardApiPost<PromptVersion>({
    path: workspacePath(session, `/prompts/templates/${templateId}/versions`),
    session,
    searchParams: tenantParams(session),
    body: payload,
  });
}

export function getPromptVersion(session: DevelopmentDashboardSession, versionId: string) {
  return dashboardApiGet<PromptVersion>({ path: workspacePath(session, `/prompts/versions/${versionId}`), session, searchParams: tenantParams(session) });
}

export function diffPromptVersions(session: DevelopmentDashboardSession, versionId: string, againstVersionId: string) {
  return dashboardApiGet<{ from_version: number; to_version: number; diff_lines: string[] }>({
    path: workspacePath(session, `/prompts/versions/${versionId}/diff`),
    session,
    searchParams: { ...tenantParams(session), against: againstVersionId },
  });
}

export function transitionPromptVersion(session: DevelopmentDashboardSession, versionId: string, newStatus: string, reason?: string) {
  return dashboardApiPost<PromptVersion>({
    path: workspacePath(session, `/prompts/versions/${versionId}/transition`),
    session,
    searchParams: tenantParams(session),
    body: { new_status: newStatus, reason: reason ?? null },
  });
}

export function evaluatePromptVersion(session: DevelopmentDashboardSession, versionId: string, datasetId: string, widgetId: string) {
  return dashboardApiPost<PromptGateVerdict>({
    path: workspacePath(session, `/prompts/versions/${versionId}/evaluate`),
    session,
    searchParams: tenantParams(session),
    body: { dataset_id: datasetId, widget_id: widgetId },
  });
}

export function renderPromptVersionPreview(session: DevelopmentDashboardSession, versionId: string) {
  return dashboardApiPost<{ rendered: string; sample_variables: Record<string, string> }>({
    path: workspacePath(session, `/prompts/versions/${versionId}/render-preview`),
    session,
    searchParams: tenantParams(session),
  });
}

export function getCompositePromptPreview(session: DevelopmentDashboardSession, widgetId?: string) {
  return dashboardApiGet<PromptCompositePreview>({
    path: workspacePath(session, "/prompts/preview"),
    session,
    searchParams: { ...tenantParams(session), widget_id: widgetId },
  });
}

export function getPromptDeployment(session: DevelopmentDashboardSession, layer: string, widgetId?: string) {
  return dashboardApiGet<PromptDeployment | null>({
    path: workspacePath(session, "/prompts/deployments"),
    session,
    searchParams: { ...tenantParams(session), layer, widget_id: widgetId },
  });
}

export function deployPromptVersion(session: DevelopmentDashboardSession, versionId: string, widgetId?: string, rolloutPercentage = 100) {
  return dashboardApiPost<PromptDeployment>({
    path: workspacePath(session, "/prompts/deployments"),
    session,
    searchParams: tenantParams(session),
    body: { version_id: versionId, widget_id: widgetId ?? null, rollout_percentage: rolloutPercentage },
  });
}

export function rollbackPromptDeployment(session: DevelopmentDashboardSession, deploymentId: string, reason?: string) {
  return dashboardApiPost<PromptDeployment>({
    path: workspacePath(session, `/prompts/deployments/${deploymentId}/rollback`),
    session,
    searchParams: tenantParams(session),
    body: { reason: reason ?? null },
  });
}

export function listPromptExperiments(session: DevelopmentDashboardSession, widgetId: string) {
  return dashboardApiGet<PromptExperiment[]>({
    path: workspacePath(session, "/prompts/experiments"),
    session,
    searchParams: { ...tenantParams(session), widget_id: widgetId },
  });
}

export function createPromptExperiment(
  session: DevelopmentDashboardSession,
  payload: {
    widget_id: string;
    layer: PromptLayer;
    control_version_id: string;
    candidate_version_id: string;
    traffic_allocation_percentage: number;
    evaluation_dataset_id?: string;
    max_duration_hours?: number;
  },
) {
  return dashboardApiPost<PromptExperiment>({
    path: workspacePath(session, "/prompts/experiments"),
    session,
    searchParams: tenantParams(session),
    body: payload,
  });
}

export function startPromptExperiment(session: DevelopmentDashboardSession, experimentId: string) {
  return dashboardApiPost<PromptExperiment>({
    path: workspacePath(session, `/prompts/experiments/${experimentId}/start`),
    session,
    searchParams: tenantParams(session),
  });
}

export function killPromptExperiment(session: DevelopmentDashboardSession, experimentId: string, reason?: string) {
  return dashboardApiPost<PromptExperiment>({
    path: workspacePath(session, `/prompts/experiments/${experimentId}/kill`),
    session,
    searchParams: tenantParams(session),
    body: { reason: reason ?? null },
  });
}

export function completePromptExperiment(session: DevelopmentDashboardSession, experimentId: string) {
  return dashboardApiPost<PromptExperiment>({
    path: workspacePath(session, `/prompts/experiments/${experimentId}/complete`),
    session,
    searchParams: tenantParams(session),
  });
}

export function getPromptExperimentMetrics(session: DevelopmentDashboardSession, experimentId: string) {
  return dashboardApiGet<ExperimentMetrics>({
    path: workspacePath(session, `/prompts/experiments/${experimentId}/metrics`),
    session,
    searchParams: tenantParams(session),
  });
}

export function listPromptAuditEvents(session: DevelopmentDashboardSession, entityId?: string) {
  return dashboardApiGet<PromptAuditEvent[]>({
    path: workspacePath(session, "/prompts/audit-events"),
    session,
    searchParams: { ...tenantParams(session), entity_id: entityId },
  });
}
