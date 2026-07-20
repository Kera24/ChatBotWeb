import { dashboardApiDelete, dashboardApiGet, dashboardApiPatch, dashboardApiPost } from "./client";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type WidgetConfigurationPayload = {
  bot_name: string;
  welcome_message: string;
  launcher_label: string;
  primary_colour: string;
  secondary_colour: string | null;
  logo_path: string | null;
  avatar_path: string | null;
  position: string;
  theme_mode: string;
  suggested_questions_json: string[];
  fallback_contact_text: string | null;
  privacy_notice_text: string | null;
  privacy_notice_url: string | null;
  terms_url: string | null;
  language: string;
  show_citations: boolean;
  allow_conversation_history: boolean;
  max_initial_suggestions: number;
};

export type WidgetRevisionDetail = {
  id: string;
  revision_number: number;
  status: string;
  is_active_published: boolean;
  concurrency_version: number;
  created_by_user_id: string | null;
  created_at: string;
  published_by_user_id: string | null;
  published_at: string | null;
  source_revision_id: string | null;
  configuration: WidgetConfigurationPayload;
};

export type WidgetSummary = {
  id: string;
  display_name: string;
  public_identifier: string;
  public_credential_id: string;
  publication_status: string;
  active_revision_number: number | null;
  active_published_revision_id: string | null;
  draft_revision_id: string | null;
  draft_dirty: boolean;
  operational_status: string;
  pilot_status: string | null;
  release_channel: string | null;
  created_at: string;
  updated_at: string;
};

export type WidgetDetail = WidgetSummary & {
  draft: WidgetRevisionDetail | null;
  active_published_revision: Omit<WidgetRevisionDetail, "configuration"> | null;
  diff: { changed_fields?: string[]; has_published_revision?: boolean } | null;
};

export type WidgetOrigin = {
  id: string;
  origin: string;
  scheme: string;
  hostname: string;
  port: number | null;
  wildcard_subdomains: boolean;
  environment: string;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type WidgetEmbedMetadata = {
  public_key: string;
  public_key_status: string;
  public_key_created_at: string;
  public_key_rotated_at: string | null;
  publication_status: string;
  published: boolean;
  operational_status: string;
  pilot_status: string;
  release_channel: string;
  version_mode: "managed_major" | "pinned" | string;
  pinned_sdk_version: string | null;
  selected_sdk_version: string;
  selected_loader_path: string;
  protocol_major: number;
  api_version: string;
  sri: string | null;
  snippet: string;
  allowed_origins: WidgetOrigin[];
  active_published_revision_id: string | null;
  active_revision_number: number | null;
  readiness: string[];
  active: boolean;
  embed_update_required: boolean;
};

export type WidgetSupportedSdkVersion = {
  version: string;
  sdk_major: number;
  protocol_major: number;
  api_version: string;
  support_status: string;
  immutable_loader_path: string;
  major_alias_path: string;
  release_channel: string | null;
  integrity: string | null;
};

export type WidgetSupportedSdkVersionsResponse = {
  recommended: string;
  versions: WidgetSupportedSdkVersion[];
};

export type WidgetCreatePayload = {
  display_name: string;
  environment?: string;
  initial_configuration?: Partial<WidgetConfigurationPayload>;
};

export type WidgetDraftUpdatePayload = Partial<WidgetConfigurationPayload> & {
  expected_concurrency_version: number;
};

export function listWidgets(session: DevelopmentDashboardSession) {
  return dashboardApiGet<WidgetSummary[]>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets`,
    session,
    searchParams: { organisation_id: session.organisationId },
  });
}

export function createWidget(session: DevelopmentDashboardSession, body: WidgetCreatePayload) {
  return dashboardApiPost<WidgetDetail>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets`,
    session,
    searchParams: { organisation_id: session.organisationId },
    body: body as Record<string, unknown>,
  });
}

export function getWidgetDetail(session: DevelopmentDashboardSession, widgetId: string) {
  return dashboardApiGet<WidgetDetail>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets/${widgetId}`,
    session,
    searchParams: { organisation_id: session.organisationId },
  });
}

export function getWidgetDraft(session: DevelopmentDashboardSession, widgetId: string) {
  return dashboardApiGet<WidgetRevisionDetail>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets/${widgetId}/draft`,
    session,
    searchParams: { organisation_id: session.organisationId },
  });
}

export function updateWidgetDraft(session: DevelopmentDashboardSession, widgetId: string, body: WidgetDraftUpdatePayload) {
  return dashboardApiPatch<WidgetRevisionDetail>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets/${widgetId}/draft`,
    session,
    searchParams: { organisation_id: session.organisationId },
    body: body as Record<string, unknown>,
  });
}

export function listWidgetOrigins(session: DevelopmentDashboardSession, widgetId: string) {
  return dashboardApiGet<WidgetOrigin[]>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets/${widgetId}/origins`,
    session,
    searchParams: { organisation_id: session.organisationId },
  });
}

export function addWidgetOrigin(session: DevelopmentDashboardSession, widgetId: string, origin: string) {
  return dashboardApiPost<WidgetOrigin>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets/${widgetId}/origins`,
    session,
    searchParams: { organisation_id: session.organisationId },
    body: { origin },
  });
}

export function removeWidgetOrigin(session: DevelopmentDashboardSession, widgetId: string, originId: string) {
  return dashboardApiDelete<WidgetOrigin>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets/${widgetId}/origins/${originId}`,
    session,
    searchParams: { organisation_id: session.organisationId },
  });
}

export function rotateWidgetPublicKey(session: DevelopmentDashboardSession, widgetId: string, expectedPublicCredentialId: string) {
  return dashboardApiPost<{
    widget_id: string;
    public_credential_id: string;
    public_key: string;
    public_key_status: string;
    old_key_revoked: boolean;
    embed_update_required: boolean;
    rotated_at: string | null;
  }>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets/${widgetId}/rotate-key`,
    session,
    searchParams: { organisation_id: session.organisationId },
    body: { expected_public_credential_id: expectedPublicCredentialId },
  });
}

export function getWidgetEmbed(session: DevelopmentDashboardSession, widgetId: string) {
  return dashboardApiGet<WidgetEmbedMetadata>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets/${widgetId}/embed`,
    session,
    searchParams: { organisation_id: session.organisationId },
  });
}

export function updateWidgetEmbedPreference(
  session: DevelopmentDashboardSession,
  widgetId: string,
  body: { version_mode: "managed_major" | "pinned"; pinned_sdk_version?: string | null },
) {
  return dashboardApiPatch<WidgetEmbedMetadata>({
    path: `/api/v1/workspaces/${session.workspaceId}/widgets/${widgetId}/embed`,
    session,
    searchParams: { organisation_id: session.organisationId },
    body,
  });
}

export function listWidgetSdkVersions(session: DevelopmentDashboardSession) {
  return dashboardApiGet<WidgetSupportedSdkVersionsResponse>({
    path: `/api/v1/workspaces/${session.workspaceId}/widget-sdk-versions`,
    session,
    searchParams: { organisation_id: session.organisationId },
  });
}

