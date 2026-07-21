import {
  ALL_WIDGET_MESSAGE_TYPES,
  MAX_PROTOCOL_ENVELOPE_BYTES,
  MAX_PROTOCOL_MESSAGE_ID_LENGTH,
  MAX_PROTOCOL_PAYLOAD_KEYS,
  MAX_PROTOCOL_STRING_LENGTH,
  SUPPORTED_WIDGET_PROTOCOL_VERSIONS,
  WIDGET_PROTOCOL_NAME,
  WIDGET_PROTOCOL_SOURCE_IFRAME,
  WIDGET_PROTOCOL_SOURCE_LOADER,
  WIDGET_PROTOCOL_VERSION,
} from "./constants";
import type {
  InitialisePayload,
  SafeProtocolError,
  WidgetProtocolEnvelope,
  WidgetProtocolMessageType,
  WidgetProtocolSource,
} from "./types";

const MESSAGE_ID_PATTERN = /^[A-Za-z0-9_-]{12,80}$/;
const FORBIDDEN_KEY_PATTERN =
  /(?:session[_-]?token|tenant|organisation|organization|workspace|api[_-]?key|secret|credential[_-]?id)/i;

export type EnvelopeValidationResult =
  | { ok: true; envelope: WidgetProtocolEnvelope }
  | { ok: false; error: SafeProtocolError };

export function createProtocolEnvelope<TPayload>(
  type: WidgetProtocolMessageType,
  source: WidgetProtocolSource,
  payload: TPayload,
  messageId = createMessageId(),
  sentAt = new Date().toISOString(),
): WidgetProtocolEnvelope<TPayload> {
  return Object.freeze({
    protocol: WIDGET_PROTOCOL_NAME,
    version: WIDGET_PROTOCOL_VERSION,
    messageId,
    type,
    source,
    payload: clonePlainPayload(payload),
    sentAt,
  });
}

export function validateProtocolEnvelope(
  value: unknown,
  options: {
    expectedSource?: WidgetProtocolSource;
    allowedTypes?: readonly WidgetProtocolMessageType[];
  } = {},
): EnvelopeValidationResult {
  if (!isPlainRecord(value)) {
    return invalid("invalid_envelope");
  }
  if (byteLength(value) > MAX_PROTOCOL_ENVELOPE_BYTES) {
    return invalid("invalid_envelope");
  }
  if (value.protocol !== WIDGET_PROTOCOL_NAME || typeof value.version !== "number") {
    return invalid("unsupported_protocol");
  }
  if (!(SUPPORTED_WIDGET_PROTOCOL_VERSIONS as readonly number[]).includes(value.version)) {
    return invalid("unsupported_protocol");
  }
  if (typeof value.messageId !== "string" || !MESSAGE_ID_PATTERN.test(value.messageId)) {
    return invalid("invalid_envelope");
  }
  if (value.messageId.length > MAX_PROTOCOL_MESSAGE_ID_LENGTH) {
    return invalid("invalid_envelope");
  }
  if (typeof value.sentAt !== "string" || Number.isNaN(Date.parse(value.sentAt))) {
    return invalid("invalid_envelope");
  }
  if (!isProtocolSource(value.source) || (options.expectedSource && value.source !== options.expectedSource)) {
    return invalid("source_mismatch");
  }
  if (!isProtocolMessageType(value.type)) {
    return invalid("invalid_envelope");
  }
  if (options.allowedTypes && !options.allowedTypes.includes(value.type)) {
    return invalid("invalid_envelope");
  }
  if (!isSafePayload(value.payload)) {
    return invalid("invalid_envelope");
  }
  return { ok: true, envelope: value as WidgetProtocolEnvelope };
}

export function validateInitialisePayload(value: unknown): value is InitialisePayload {
  if (!isPlainRecord(value)) {
    return false;
  }
  const keys = Object.keys(value);
  if (keys.length > 9 || keys.some((key) => FORBIDDEN_KEY_PATTERN.test(key))) {
    return false;
  }
  return (
    typeof value.widgetKey === "string" &&
    /^wpk_(dev|stg|live)_[A-Za-z0-9_-]{16,96}$/.test(value.widgetKey) &&
    typeof value.parentOrigin === "string" &&
    isSafeOrigin(value.parentOrigin) &&
    typeof value.sdkVersion === "string" &&
    value.sdkVersion.length <= 64 &&
    value.protocolVersion === WIDGET_PROTOCOL_VERSION &&
    ["development", "staging", "production"].includes(String(value.environment)) &&
    typeof value.initialOpen === "boolean" &&
    ["floating", "inline"].includes(String(value.mountMode)) &&
    (value.localeHint === undefined || (typeof value.localeHint === "string" && value.localeHint.length <= 35)) &&
    typeof value.debug === "boolean"
  );
}

export function createSafeProtocolError(
  code: SafeProtocolError["code"],
  phase: SafeProtocolError["phase"] = "protocol",
  retryable = false,
): SafeProtocolError {
  const messages: Record<SafeProtocolError["code"], string> = {
    invalid_envelope: "The widget protocol message is invalid.",
    unsupported_protocol: "The widget protocol is not supported.",
    origin_mismatch: "The widget message origin is invalid.",
    source_mismatch: "The widget message source is invalid.",
    invalid_parent_origin: "The widget parent origin is invalid.",
    handshake_timeout: "The widget handshake timed out.",
    duplicate_initialise: "The widget has already been initialised.",
    invalid_state: "The widget is not in a valid state for this operation.",
    iframe_unavailable: "The widget iframe is unavailable.",
    destroyed: "The widget has been destroyed.",
    safe_internal_error: "The widget could not complete the operation.",
  };
  return Object.freeze({ code, message: messages[code], retryable, phase });
}

export function createMessageId(): string {
  const cryptoObject = globalThis.crypto as (Crypto & { randomUUID?: () => string }) | undefined;
  if (cryptoObject?.randomUUID) {
    return cryptoObject.randomUUID().replace(/-/g, "");
  }
  const bytes = new Uint8Array(16);
  if (cryptoObject?.getRandomValues) {
    cryptoObject.getRandomValues(bytes);
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function invalid(code: SafeProtocolError["code"]): EnvelopeValidationResult {
  return { ok: false, error: createSafeProtocolError(code) };
}

function isProtocolSource(value: unknown): value is WidgetProtocolSource {
  return value === WIDGET_PROTOCOL_SOURCE_LOADER || value === WIDGET_PROTOCOL_SOURCE_IFRAME;
}

function isProtocolMessageType(value: unknown): value is WidgetProtocolMessageType {
  return typeof value === "string" && (ALL_WIDGET_MESSAGE_TYPES as readonly string[]).includes(value);
}

function isSafePayload(value: unknown, depth = 0): boolean {
  if (depth > 2) {
    return false;
  }
  if (value === null || typeof value === "boolean") {
    return true;
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (typeof value === "string") {
    return value.length <= MAX_PROTOCOL_STRING_LENGTH && !value.includes("\0");
  }
  if (Array.isArray(value)) {
    return value.length <= 16 && value.every((item) => isSafePayload(item, depth + 1));
  }
  if (!isPlainRecord(value)) {
    return false;
  }
  const keys = Object.keys(value);
  return (
    keys.length <= MAX_PROTOCOL_PAYLOAD_KEYS &&
    keys.every((key) => key.length <= 80 && !FORBIDDEN_KEY_PATTERN.test(key) && isSafePayload(value[key], depth + 1))
  );
}

function clonePlainPayload<TPayload>(payload: TPayload): TPayload {
  if (!isSafePayload(payload)) {
    throw createSafeProtocolError("invalid_envelope");
  }
  return JSON.parse(JSON.stringify(payload)) as TPayload;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype;
}

function byteLength(value: unknown): number {
  return new TextEncoder().encode(JSON.stringify(value)).length;
}

function isSafeOrigin(value: string): boolean {
  try {
    const parsed = new URL(value);
    return (parsed.protocol === "https:" || parsed.protocol === "http:") && parsed.origin === value && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}

