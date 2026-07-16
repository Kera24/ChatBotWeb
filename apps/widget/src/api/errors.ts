export type WidgetApiErrorCode =
  | "configuration_unavailable"
  | "invalid_widget"
  | "origin_denied"
  | "rate_limited"
  | "session_creation_failed"
  | "invalid_session"
  | "session_expired"
  | "session_limit_reached"
  | "message_rejected"
  | "unsafe_request"
  | "quota_exceeded"
  | "request_in_progress"
  | "network_error"
  | "request_timeout"
  | "incompatible_response"
  | "storage_unavailable"
  | "secure_random_unavailable"
  | "temporarily_unavailable"
  | "safe_internal_error";

export type WidgetApiPhase = "configuration" | "session" | "message" | "storage" | "bootstrap" | "network";

export type SafeWidgetApiErrorShape = Readonly<{
  code: WidgetApiErrorCode;
  message: string;
  retryable: boolean;
  phase: WidgetApiPhase;
  requestId?: string;
  retryAfterSeconds?: number;
}>;

const DEFAULT_MESSAGES: Record<WidgetApiErrorCode, string> = {
  configuration_unavailable: "Widget configuration is unavailable.",
  invalid_widget: "Widget is unavailable.",
  origin_denied: "Widget is unavailable for this site.",
  rate_limited: "Too many requests. Please try again later.",
  session_creation_failed: "Could not start a widget session.",
  invalid_session: "Widget session is no longer valid.",
  session_expired: "Widget session has expired.",
  session_limit_reached: "This widget session has reached its message limit.",
  message_rejected: "Message could not be sent.",
  unsafe_request: "Message could not be sent.",
  quota_exceeded: "Message limit is temporarily reached.",
  request_in_progress: "A matching request is still in progress.",
  network_error: "Network connection failed.",
  request_timeout: "Request timed out.",
  incompatible_response: "Widget service returned an incompatible response.",
  storage_unavailable: "Browser storage is unavailable.",
  secure_random_unavailable: "Secure browser randomness is unavailable.",
  temporarily_unavailable: "Widget service is temporarily unavailable.",
  safe_internal_error: "Widget service failed safely.",
};

export class WidgetApiError extends Error {
  readonly code: WidgetApiErrorCode;
  readonly retryable: boolean;
  readonly phase: WidgetApiPhase;
  readonly requestId?: string;
  readonly retryAfterSeconds?: number;

  constructor(code: WidgetApiErrorCode, phase: WidgetApiPhase, options: { retryable?: boolean; requestId?: string; retryAfterSeconds?: number; message?: string } = {}) {
    super(options.message ?? DEFAULT_MESSAGES[code]);
    this.name = "WidgetApiError";
    this.code = code;
    this.phase = phase;
    this.retryable = options.retryable ?? ["network_error", "request_timeout", "temporarily_unavailable", "request_in_progress", "rate_limited"].includes(code);
    this.requestId = options.requestId;
    this.retryAfterSeconds = options.retryAfterSeconds;
  }

  toSafeShape(): SafeWidgetApiErrorShape {
    return Object.freeze({
      code: this.code,
      message: this.message,
      retryable: this.retryable,
      phase: this.phase,
      requestId: this.requestId,
      retryAfterSeconds: this.retryAfterSeconds,
    });
  }
}

export function toWidgetApiError(error: unknown, fallbackPhase: WidgetApiPhase): WidgetApiError {
  if (error instanceof WidgetApiError) {
    return error;
  }
  return new WidgetApiError("safe_internal_error", fallbackPhase, { retryable: false });
}
