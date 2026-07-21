import { MAX_LOCALE_HINT_LENGTH, MAX_NONCE_LENGTH, SUPPORTED_MOUNT_MODES } from "./constants";
import { createSDKError, WidgetSDKError, type WidgetSDKErrorCode } from "./errors";
import { isWidgetEnvironment, resolveWidgetEnvironment, type ResolvedWidgetEnvironment, type WidgetEnvironment } from "./environment";

export type WidgetMountMode = (typeof SUPPORTED_MOUNT_MODES)[number];

export type WidgetSDKConfig = {
  widgetKey: string;
  environment?: WidgetEnvironment;
  initialOpen?: boolean;
  mountMode?: WidgetMountMode;
  container?: string | Element;
  localeHint?: string;
  debug?: boolean;
  sdkHost?: string;
  iframeHost?: string;
  nonce?: string;
};

export type ValidatedWidgetSDKConfig = Readonly<{
  widgetKey: string;
  environment: WidgetEnvironment;
  initialOpen: boolean;
  mountMode: WidgetMountMode;
  container?: string | Element;
  localeHint?: string;
  debug: boolean;
  nonce?: string;
  hosts: ResolvedWidgetEnvironment;
}>;

const ALLOWED_FIELDS = new Set([
  "widgetKey",
  "environment",
  "initialOpen",
  "mountMode",
  "container",
  "localeHint",
  "debug",
  "sdkHost",
  "iframeHost",
  "nonce",
]);

const KEY_PATTERN = /^wpk_(dev|stg|live)_[A-Za-z0-9_-]{16,96}$/;
const ENVIRONMENT_BY_PREFIX: Record<string, WidgetEnvironment> = {
  dev: "development",
  stg: "staging",
  live: "production",
};
const LOCALE_PATTERN = /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,2}$/;
const NONCE_PATTERN = /^[A-Za-z0-9+/_=-]+$/;

export type ConfigValidationResult =
  | { ok: true; config: ValidatedWidgetSDKConfig }
  | { ok: false; error: WidgetSDKError };

export function validateWidgetSDKConfig(input: unknown): ConfigValidationResult {
  if (!isRecord(input)) {
    return fail("invalid_configuration");
  }
  const unknownField = Object.keys(input).find((key) => !ALLOWED_FIELDS.has(key));
  if (unknownField) {
    return fail("invalid_configuration", { field: unknownField });
  }
  if (typeof input.widgetKey !== "string" || input.widgetKey.trim() === "") {
    return fail("invalid_widget_key");
  }
  const widgetKey = input.widgetKey.trim();
  const match = KEY_PATTERN.exec(widgetKey);
  if (!match) {
    return fail("invalid_widget_key");
  }
  const keyEnvironment = ENVIRONMENT_BY_PREFIX[match[1] ?? ""];
  const environment = input.environment ?? keyEnvironment;
  if (!isWidgetEnvironment(environment)) {
    return fail("unsupported_environment");
  }
  if (environment !== keyEnvironment) {
    return fail("environment_mismatch", { keyEnvironment, environment });
  }
  const mountMode = input.mountMode ?? "floating";
  if (typeof mountMode !== "string" || !(SUPPORTED_MOUNT_MODES as readonly string[]).includes(mountMode)) {
    return fail("invalid_configuration", { field: "mountMode" });
  }
  if (input.initialOpen !== undefined && typeof input.initialOpen !== "boolean") {
    return fail("invalid_configuration", { field: "initialOpen" });
  }
  if (input.debug !== undefined && typeof input.debug !== "boolean") {
    return fail("invalid_configuration", { field: "debug" });
  }
  const debug = input.debug ?? false;
  if (debug && environment !== "development") {
    return fail("invalid_configuration", { field: "debug" });
  }
  if (input.localeHint !== undefined && !isValidLocaleHint(input.localeHint)) {
    return fail("invalid_configuration", { field: "localeHint" });
  }
  if (input.nonce !== undefined && !isValidNonce(input.nonce)) {
    return fail("invalid_configuration", { field: "nonce" });
  }
  if (input.container !== undefined && typeof input.container !== "string" && !isElementLike(input.container)) {
    return fail("invalid_configuration", { field: "container" });
  }
  if (environment !== "development" && (input.sdkHost !== undefined || input.iframeHost !== undefined)) {
    return fail("insecure_host", { field: "hostOverride" });
  }
  const hosts = resolveWidgetEnvironment(environment, {
    sdkHost: typeof input.sdkHost === "string" ? input.sdkHost : undefined,
    iframeHost: typeof input.iframeHost === "string" ? input.iframeHost : undefined,
  });
  if (hosts instanceof WidgetSDKError) {
    return { ok: false, error: hosts };
  }
  return {
    ok: true,
    config: Object.freeze({
      widgetKey,
      environment,
      initialOpen: input.initialOpen ?? false,
      mountMode: mountMode as WidgetMountMode,
      ...(input.container !== undefined ? { container: input.container as string | Element } : {}),
      ...(typeof input.localeHint === "string" ? { localeHint: input.localeHint } : {}),
      debug,
      ...(typeof input.nonce === "string" ? { nonce: input.nonce } : {}),
      hosts,
    }),
  };
}

export function assertValidWidgetSDKConfig(input: unknown): ValidatedWidgetSDKConfig {
  const result = validateWidgetSDKConfig(input);
  if (!result.ok) {
    throw result.error;
  }
  return result.config;
}

function fail(code: WidgetSDKErrorCode, metadata: Record<string, string | boolean> = {}): ConfigValidationResult {
  return { ok: false, error: createSDKError(code, "configuration", { safeMetadata: metadata }) };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isElementLike(value: unknown): boolean {
  return isRecord(value) && value.nodeType === 1;
}

function isValidLocaleHint(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= MAX_LOCALE_HINT_LENGTH && LOCALE_PATTERN.test(value);
}

function isValidNonce(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= MAX_NONCE_LENGTH && NONCE_PATTERN.test(value);
}