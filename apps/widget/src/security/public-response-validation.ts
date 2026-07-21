import {
  CONFIG_RESPONSE_SCHEMA_VERSION,
  MESSAGE_RESPONSE_SCHEMA_VERSION,
  STORED_SESSION_SCHEMA_VERSION,
  type CachedConfigRecord,
  type PublicCitation,
  type PublicMessageResponse,
  type PublicSessionResponse,
  type PublicWidgetConfigResponse,
  type StoredSessionRecord,
} from "../api/contracts";
import { WidgetApiError } from "../api/errors";

const FORBIDDEN_KEYS = [
  "organisation_id",
  "organization_id",
  "workspace_id",
  "credential_id",
  "conversation_id",
  "internal_session_id",
  "public_token_id",
  "token_hash",
  "token_secret_hash",
  "provider",
  "model",
  "prompt",
  "execution_id",
  "allowed_origins",
  "metadata_json",
];

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}T/;
const COLOUR_RE = /^#[0-9a-fA-F]{6}$/;
const TOKEN_RE = /^pss_(dev|stg|live)_[A-Za-z0-9_-]{16,96}\.[A-Za-z0-9_-]{24,160}$/;

export function validateConfigResponse(value: unknown): PublicWidgetConfigResponse {
  assertPlainObject(value);
  assertNoForbiddenKeys(value, ["session_token"]);
  const candidate = value as Record<string, unknown>;
  const widget = requireObject(candidate.widget, "widget");
  const behaviour = requireObject(candidate.behaviour, "behaviour");
  const privacy = requireObject(candidate.privacy, "privacy");
  const capabilities = requireObject(candidate.capabilities, "capabilities");
  const response: PublicWidgetConfigResponse = Object.freeze({
    widget: {
      bot_name: boundedString(widget.bot_name, 1, 120, "bot_name"),
      welcome_message: boundedString(widget.welcome_message, 0, 1000, "welcome_message"),
      launcher_label: boundedString(widget.launcher_label, 1, 80, "launcher_label"),
      primary_colour: colour(widget.primary_colour, "primary_colour"),
      secondary_colour: nullableColour(widget.secondary_colour, "secondary_colour"),
      logo_url: nullableHttpsUrl(widget.logo_url, "logo_url"),
      avatar_url: nullableHttpsUrl(widget.avatar_url, "avatar_url"),
      position: boundedString(widget.position, 1, 40, "position"),
      theme_mode: boundedString(widget.theme_mode, 1, 30, "theme_mode"),
      language: boundedString(widget.language, 1, 35, "language"),
    },
    behaviour: {
      suggested_questions: stringArray(behaviour.suggested_questions, 8, 180, "suggested_questions"),
      max_initial_suggestions: boundedInteger(behaviour.max_initial_suggestions, 0, 8, "max_initial_suggestions"),
      show_citations: booleanValue(behaviour.show_citations, "show_citations"),
      allow_conversation_history: booleanValue(behaviour.allow_conversation_history, "allow_conversation_history"),
      session_required: booleanValue(behaviour.session_required, "session_required"),
      messages_enabled: booleanValue(behaviour.messages_enabled, "messages_enabled"),
    },
    privacy: {
      privacy_notice_text: nullableString(privacy.privacy_notice_text, 1200, "privacy_notice_text"),
      privacy_notice_url: nullableHttpsUrl(privacy.privacy_notice_url, "privacy_notice_url"),
      terms_url: nullableHttpsUrl(privacy.terms_url, "terms_url"),
      fallback_contact_text: nullableString(privacy.fallback_contact_text, 600, "fallback_contact_text"),
    },
    capabilities: {
      can_create_session: booleanValue(capabilities.can_create_session, "can_create_session"),
      can_send_messages: booleanValue(capabilities.can_send_messages, "can_send_messages"),
      citations_enabled: booleanValue(capabilities.citations_enabled, "citations_enabled"),
      conversation_history_enabled: booleanValue(capabilities.conversation_history_enabled, "conversation_history_enabled"),
    },
    configuration_version: boundedInteger(candidate.configuration_version, 1, Number.MAX_SAFE_INTEGER, "configuration_version"),
    response_schema_version: literal(candidate.response_schema_version, CONFIG_RESPONSE_SCHEMA_VERSION, "response_schema_version"),
    published_at: nullableTimestamp(candidate.published_at, "published_at"),
    request_id: boundedString(candidate.request_id, 1, 128, "request_id"),
  });
  return response;
}

export function validateSessionResponse(value: unknown): PublicSessionResponse {
  assertPlainObject(value);
  assertNoForbiddenKeys(value);
  const candidate = value as Record<string, unknown>;
  const capabilities = requireObject(candidate.capabilities, "capabilities");
  const token = boundedString(candidate.session_token, 40, 280, "session_token");
  if (!TOKEN_RE.test(token)) {
    throw incompatible("session_token");
  }
  return Object.freeze({
    session_token: token,
    expires_at: timestamp(candidate.expires_at, "expires_at"),
    absolute_expires_at: timestamp(candidate.absolute_expires_at, "absolute_expires_at"),
    inactivity_timeout_seconds: boundedInteger(candidate.inactivity_timeout_seconds, 1, 86400, "inactivity_timeout_seconds"),
    max_messages: boundedInteger(candidate.max_messages, 0, 10000, "max_messages"),
    remaining_messages: boundedInteger(candidate.remaining_messages, 0, 10000, "remaining_messages"),
    configuration_version: boundedInteger(candidate.configuration_version, 1, Number.MAX_SAFE_INTEGER, "configuration_version"),
    capabilities: {
      can_send_messages: booleanValue(capabilities.can_send_messages, "can_send_messages"),
      conversation_history_enabled: booleanValue(capabilities.conversation_history_enabled, "conversation_history_enabled"),
      citations_enabled: booleanValue(capabilities.citations_enabled, "citations_enabled"),
    },
    request_id: boundedString(candidate.request_id, 1, 128, "request_id"),
  });
}

export function validateMessageResponse(value: unknown): PublicMessageResponse {
  assertPlainObject(value);
  assertNoForbiddenKeys(value, ["session_token"]);
  const candidate = value as Record<string, unknown>;
  return Object.freeze({
    response_id: boundedString(candidate.response_id, 1, 160, "response_id"),
    answer: boundedString(candidate.answer, 0, 12000, "answer"),
    answer_state: enumValue(candidate.answer_state, ["answered", "fallback", "low_confidence", "temporarily_unavailable"], "answer_state"),
    citations: citations(candidate.citations),
    remaining_messages: boundedInteger(candidate.remaining_messages, 0, 10000, "remaining_messages"),
    session_expires_at: timestamp(candidate.session_expires_at, "session_expires_at"),
    fallback_used: booleanValue(candidate.fallback_used, "fallback_used"),
    request_id: boundedString(candidate.request_id, 1, 128, "request_id"),
    response_schema_version: literal(candidate.response_schema_version, MESSAGE_RESPONSE_SCHEMA_VERSION, "response_schema_version"),
  });
}

export function validateStoredSessionRecord(value: unknown): StoredSessionRecord {
  assertPlainObject(value);
  const candidate = value as Record<string, unknown>;
  const token = boundedString(candidate.sessionToken, 40, 280, "sessionToken");
  if (!TOKEN_RE.test(token)) throw incompatible("sessionToken");
  return Object.freeze({
    sessionToken: token,
    expiresAt: timestamp(candidate.expiresAt, "expiresAt"),
    absoluteExpiresAt: timestamp(candidate.absoluteExpiresAt, "absoluteExpiresAt"),
    remainingMessages: boundedInteger(candidate.remainingMessages, 0, 10000, "remainingMessages"),
    configurationVersion: boundedInteger(candidate.configurationVersion, 1, Number.MAX_SAFE_INTEGER, "configurationVersion"),
    createdAt: timestamp(candidate.createdAt, "createdAt"),
    schemaVersion: literal(candidate.schemaVersion, STORED_SESSION_SCHEMA_VERSION, "schemaVersion"),
  });
}

export function validateCachedConfigRecord(value: unknown): CachedConfigRecord {
  assertPlainObject(value);
  const candidate = value as Record<string, unknown>;
  return Object.freeze({
    schemaVersion: literal(candidate.schemaVersion, "1.0", "schemaVersion"),
    etag: nullableString(candidate.etag, 128, "etag"),
    cachedAt: timestamp(candidate.cachedAt, "cachedAt"),
    config: validateConfigResponse(candidate.config),
  });
}

function citations(value: unknown): readonly PublicCitation[] {
  if (!Array.isArray(value) || value.length > 10) throw incompatible("citations");
  return Object.freeze(value.map((entry, index) => {
    assertPlainObject(entry);
    const candidate = entry as Record<string, unknown>;
    return Object.freeze({
      citation_index: boundedInteger(candidate.citation_index, 1, 99, `citations.${index}.citation_index`),
      source_title: boundedString(candidate.source_title, 1, 220, `citations.${index}.source_title`),
      source_type: boundedString(candidate.source_type, 1, 80, `citations.${index}.source_type`),
      page_number: nullableInteger(candidate.page_number, 1, 100000, `citations.${index}.page_number`),
      section_title: nullableString(candidate.section_title, 220, `citations.${index}.section_title`),
      quoted_text: nullableString(candidate.quoted_text, 600, `citations.${index}.quoted_text`),
    });
  }));
}

function assertPlainObject(value: unknown): asserts value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) {
    throw incompatible("response");
  }
}

function assertNoForbiddenKeys(value: unknown, extra: readonly string[] = []): void {
  if (!value || typeof value !== "object") return;
  const forbidden = new Set([...FORBIDDEN_KEYS, ...extra]);
  for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
    if (forbidden.has(key)) throw incompatible(key);
    assertNoForbiddenKeys(entry, extra);
  }
}

function requireObject(value: unknown, field: string): Record<string, unknown> {
  assertPlainObject(value);
  if (!value) throw incompatible(field);
  return value;
}

function boundedString(value: unknown, min: number, max: number, field: string): string {
  if (typeof value !== "string" || value.length < min || value.length > max) throw incompatible(field);
  return value;
}

function nullableString(value: unknown, max: number, field: string): string | null {
  if (value === null || value === undefined) return null;
  return boundedString(value, 0, max, field);
}

function stringArray(value: unknown, maxItems: number, maxLength: number, field: string): readonly string[] {
  if (!Array.isArray(value) || value.length > maxItems) throw incompatible(field);
  return Object.freeze(value.map((entry, index) => boundedString(entry, 1, maxLength, `${field}.${index}`)));
}

function booleanValue(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") throw incompatible(field);
  return value;
}

function boundedInteger(value: unknown, min: number, max: number, field: string): number {
  if (!Number.isInteger(value) || (value as number) < min || (value as number) > max) throw incompatible(field);
  return value as number;
}

function nullableInteger(value: unknown, min: number, max: number, field: string): number | null {
  if (value === null || value === undefined) return null;
  return boundedInteger(value, min, max, field);
}

function timestamp(value: unknown, field: string): string {
  const candidate = boundedString(value, 1, 80, field);
  if (!ISO_DATE_RE.test(candidate) || Number.isNaN(Date.parse(candidate))) throw incompatible(field);
  return candidate;
}

function nullableTimestamp(value: unknown, field: string): string | null {
  if (value === null || value === undefined) return null;
  return timestamp(value, field);
}

function colour(value: unknown, field: string): string {
  const candidate = boundedString(value, 7, 7, field);
  if (!COLOUR_RE.test(candidate)) throw incompatible(field);
  return candidate;
}

function nullableColour(value: unknown, field: string): string | null {
  if (value === null || value === undefined) return null;
  return colour(value, field);
}

function nullableHttpsUrl(value: unknown, field: string): string | null {
  if (value === null || value === undefined) return null;
  const candidate = boundedString(value, 8, 2048, field);
  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    throw incompatible(field);
  }
  if (parsed.protocol !== "https:" || parsed.username || parsed.password) throw incompatible(field);
  return parsed.toString();
}

function enumValue<T extends string>(value: unknown, allowed: readonly T[], field: string): T {
  if (typeof value !== "string" || !allowed.includes(value as T)) throw incompatible(field);
  return value as T;
}

function literal<T extends string>(value: unknown, expected: T, field: string): T {
  if (value !== expected) throw incompatible(field);
  return expected;
}

function incompatible(field: string): WidgetApiError {
  return new WidgetApiError("incompatible_response", "network", { retryable: false, message: `Incompatible widget response: ${field}.` });
}
