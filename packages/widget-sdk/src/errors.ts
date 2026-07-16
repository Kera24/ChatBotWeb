export type WidgetSDKErrorCode =
  | "invalid_configuration"
  | "invalid_widget_key"
  | "environment_mismatch"
  | "unsupported_environment"
  | "insecure_host"
  | "duplicate_initialisation"
  | "sdk_not_ready"
  | "iframe_load_failed"
  | "protocol_mismatch"
  | "destroyed"
  | "unsupported_browser"
  | "safe_internal_error";

export type WidgetSDKErrorPhase = "configuration" | "bootstrap" | "runtime" | "iframe" | "protocol";

const SAFE_MESSAGES: Record<WidgetSDKErrorCode, string> = {
  invalid_configuration: "The widget configuration is invalid.",
  invalid_widget_key: "The widget key is invalid.",
  environment_mismatch: "The widget key does not match the selected environment.",
  unsupported_environment: "The selected widget environment is not supported.",
  insecure_host: "The widget host configuration is not secure.",
  duplicate_initialisation: "The widget has already been initialised.",
  sdk_not_ready: "The widget SDK is not ready yet.",
  iframe_load_failed: "The widget could not be loaded.",
  protocol_mismatch: "The widget version is not compatible with this SDK.",
  destroyed: "The widget SDK has been destroyed.",
  unsupported_browser: "This browser is not supported by the widget SDK.",
  safe_internal_error: "The widget SDK could not complete the operation.",
};

export type WidgetSDKErrorPublic = {
  code: WidgetSDKErrorCode;
  message: string;
  retryable: boolean;
  phase: WidgetSDKErrorPhase;
  metadata?: Record<string, string | number | boolean>;
};

export class WidgetSDKError extends Error {
  public readonly code: WidgetSDKErrorCode;
  public readonly retryable: boolean;
  public readonly phase: WidgetSDKErrorPhase;
  public readonly safeMetadata?: Record<string, string | number | boolean>;
  public readonly internalCause?: unknown;

  constructor(
    code: WidgetSDKErrorCode,
    options: {
      phase: WidgetSDKErrorPhase;
      retryable?: boolean;
      cause?: unknown;
      safeMetadata?: Record<string, string | number | boolean>;
    },
  ) {
    super(SAFE_MESSAGES[code]);
    this.name = "WidgetSDKError";
    this.code = code;
    this.phase = options.phase;
    this.retryable = options.retryable ?? false;
    this.safeMetadata = options.safeMetadata;
    this.internalCause = options.cause;
  }

  toPublicJSON(): WidgetSDKErrorPublic {
    return {
      code: this.code,
      message: this.message,
      retryable: this.retryable,
      phase: this.phase,
      ...(this.safeMetadata ? { metadata: this.safeMetadata } : {}),
    };
  }
}

export function createSDKError(
  code: WidgetSDKErrorCode,
  phase: WidgetSDKErrorPhase,
  options: { retryable?: boolean; cause?: unknown; safeMetadata?: Record<string, string | number | boolean> } = {},
): WidgetSDKError {
  return new WidgetSDKError(code, { phase, ...options });
}