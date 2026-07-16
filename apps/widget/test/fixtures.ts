export const validConfig = {
  widget: {
    bot_name: "Yoranix",
    welcome_message: "Hello",
    launcher_label: "Chat",
    primary_colour: "#123456",
    secondary_colour: null,
    logo_url: "https://cdn.example/logo.png",
    avatar_url: null,
    position: "bottom-right",
    theme_mode: "light",
    language: "en",
  },
  behaviour: {
    suggested_questions: ["What can you do?"],
    max_initial_suggestions: 1,
    show_citations: true,
    allow_conversation_history: false,
    session_required: true,
    messages_enabled: true,
  },
  privacy: {
    privacy_notice_text: null,
    privacy_notice_url: "https://example.com/privacy",
    terms_url: null,
    fallback_contact_text: null,
  },
  capabilities: {
    can_create_session: true,
    can_send_messages: true,
    citations_enabled: true,
    conversation_history_enabled: false,
  },
  configuration_version: 3,
  response_schema_version: "1.0",
  published_at: "2026-07-16T00:00:00.000Z",
  request_id: "req_123",
} as const;

export const validSession = {
  session_token: "pss_dev_abcdefghijklmnop.abcdefghijklmnopqrstuvwx",
  expires_at: "2026-07-16T01:00:00.000Z",
  absolute_expires_at: "2026-07-16T02:00:00.000Z",
  inactivity_timeout_seconds: 1800,
  max_messages: 20,
  remaining_messages: 19,
  configuration_version: 3,
  capabilities: {
    can_send_messages: true,
    conversation_history_enabled: false,
    citations_enabled: true,
  },
  request_id: "req_sess",
} as const;

export const validMessage = {
  response_id: "resp_1",
  answer: "Safe answer",
  answer_state: "answered",
  citations: [],
  remaining_messages: 18,
  session_expires_at: "2026-07-16T01:10:00.000Z",
  fallback_used: false,
  request_id: "req_msg",
  response_schema_version: "1.0",
} as const;

export function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), {
    ...init,
    status: init.status ?? 200,
    headers,
  });
}