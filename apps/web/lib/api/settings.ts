import { dashboardApiGet, dashboardApiPatch } from "./client";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type SettingsWorkspace = {
  id: string;
  organisation_id: string;
  name: string;
  slug: string;
  status: string;
  default_language: string;
  created_at: string;
  updated_at: string;
};

export type SettingsOrganisation = {
  id: string;
  name: string;
  slug: string;
  status: string;
  plan_key: string;
  created_at: string;
  updated_at: string;
};

export type SettingsMembershipSummary = {
  total: number;
  active: number;
  inactive: number;
  administrators: number;
};

export type SettingsOperational = {
  environment: string;
  service_name: string;
  version: string;
  phase: string;
  public_widgets_enabled: boolean;
  public_widget_messages_enabled: boolean;
  public_widget_pilot_enforcement_enabled: boolean;
  retrieval_max_context_chunks: number;
  retrieval_max_context_chars: number;
  chunk_size_words: number;
  chunk_overlap_words: number;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimension: number;
  default_ai_provider_key: string;
  default_ai_model_key: string;
  ai_request_timeout_seconds: number;
};

export type SettingsCapabilities = {
  editable_fields: string[];
  read_only_fields: string[];
  environment_controlled_fields: string[];
  secret_managed_fields: string[];
  unsupported_fields: string[];
};

export type WorkspaceSettings = {
  workspace: SettingsWorkspace;
  organisation: SettingsOrganisation;
  membership_summary: SettingsMembershipSummary;
  operational: SettingsOperational;
  capabilities: SettingsCapabilities;
};

export type WorkspaceSettingsUpdate = {
  name: string;
  default_language: string;
  expected_updated_at?: string;
};

function workspacePath(session: DevelopmentDashboardSession, suffix: string) {
  return `/api/v1/workspaces/${session.workspaceId}${suffix}`;
}

function tenantParams(session: DevelopmentDashboardSession) {
  return { organisation_id: session.organisationId };
}

export function getWorkspaceSettings(session: DevelopmentDashboardSession) {
  return dashboardApiGet<WorkspaceSettings>({
    path: workspacePath(session, "/settings"),
    session,
    searchParams: tenantParams(session),
  });
}

export function updateWorkspaceSettings(session: DevelopmentDashboardSession, payload: WorkspaceSettingsUpdate) {
  return dashboardApiPatch<WorkspaceSettings>({
    path: workspacePath(session, "/settings"),
    session,
    searchParams: tenantParams(session),
    body: payload,
  });
}
