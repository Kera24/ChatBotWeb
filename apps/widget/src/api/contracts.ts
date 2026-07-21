export const CONFIG_RESPONSE_SCHEMA_VERSION = "1.0";
export const MESSAGE_RESPONSE_SCHEMA_VERSION = "1.0";
export const STORED_SESSION_SCHEMA_VERSION = "1.0";

export type PublicWidgetConfigResponse = Readonly<{
  widget: {
    bot_name: string;
    welcome_message: string;
    launcher_label: string;
    primary_colour: string;
    secondary_colour: string | null;
    logo_url: string | null;
    avatar_url: string | null;
    position: string;
    theme_mode: string;
    language: string;
  };
  behaviour: {
    suggested_questions: readonly string[];
    max_initial_suggestions: number;
    show_citations: boolean;
    allow_conversation_history: boolean;
    session_required: boolean;
    messages_enabled: boolean;
  };
  privacy: {
    privacy_notice_text: string | null;
    privacy_notice_url: string | null;
    terms_url: string | null;
    fallback_contact_text: string | null;
  };
  capabilities: {
    can_create_session: boolean;
    can_send_messages: boolean;
    citations_enabled: boolean;
    conversation_history_enabled: boolean;
  };
  configuration_version: number;
  response_schema_version: typeof CONFIG_RESPONSE_SCHEMA_VERSION;
  published_at: string | null;
  request_id: string;
}>;

export type PublicSessionResponse = Readonly<{
  session_token: string;
  expires_at: string;
  absolute_expires_at: string;
  inactivity_timeout_seconds: number;
  max_messages: number;
  remaining_messages: number;
  configuration_version: number;
  capabilities: {
    can_send_messages: boolean;
    conversation_history_enabled: boolean;
    citations_enabled: boolean;
  };
  request_id: string;
}>;

export type PublicCitation = Readonly<{
  citation_index: number;
  source_title: string;
  source_type: string;
  page_number?: number | null;
  section_title?: string | null;
  quoted_text?: string | null;
}>;

export type PublicMessageResponse = Readonly<{
  response_id: string;
  answer: string;
  answer_state: "answered" | "fallback" | "low_confidence" | "temporarily_unavailable";
  citations: readonly PublicCitation[];
  remaining_messages: number;
  session_expires_at: string;
  fallback_used: boolean;
  request_id: string;
  response_schema_version: typeof MESSAGE_RESPONSE_SCHEMA_VERSION;
}>;

export type SafeErrorResponse = Readonly<{
  code: string;
  message: string;
  retryable: boolean;
  request_id?: string;
  retry_after_seconds?: number;
}>;

export type StoredSessionRecord = Readonly<{
  sessionToken: string;
  expiresAt: string;
  absoluteExpiresAt: string;
  remainingMessages: number;
  configurationVersion: number;
  createdAt: string;
  schemaVersion: typeof STORED_SESSION_SCHEMA_VERSION;
}>;

export type CachedConfigRecord = Readonly<{
  schemaVersion: "1.0";
  etag: string | null;
  cachedAt: string;
  config: PublicWidgetConfigResponse;
}>;
