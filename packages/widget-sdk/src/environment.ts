import { DEFAULT_API_HOSTS, DEFAULT_IFRAME_HOSTS, DEFAULT_SDK_HOSTS, SUPPORTED_ENVIRONMENTS } from "./constants";
import { createSDKError, WidgetSDKError } from "./errors";

export type WidgetEnvironment = (typeof SUPPORTED_ENVIRONMENTS)[number];

export type ResolvedWidgetEnvironment = Readonly<{
  environment: WidgetEnvironment;
  sdkHost: string;
  iframeHost: string;
  apiHost: string;
}>;

export function isWidgetEnvironment(value: unknown): value is WidgetEnvironment {
  return typeof value === "string" && (SUPPORTED_ENVIRONMENTS as readonly string[]).includes(value);
}

export function resolveWidgetEnvironment(
  environment: WidgetEnvironment,
  overrides: { sdkHost?: string; iframeHost?: string; apiHost?: string } = {},
): ResolvedWidgetEnvironment | WidgetSDKError {
  if (!isWidgetEnvironment(environment)) {
    return createSDKError("unsupported_environment", "configuration", { safeMetadata: { environment: String(environment) } });
  }
  const sdkHost = overrides.sdkHost ?? DEFAULT_SDK_HOSTS[environment];
  const iframeHost = overrides.iframeHost ?? DEFAULT_IFRAME_HOSTS[environment];
  const apiHost = overrides.apiHost ?? DEFAULT_API_HOSTS[environment];
  const normalised = {
    sdkHost: normaliseHostUrl(sdkHost, environment),
    iframeHost: normaliseHostUrl(iframeHost, environment),
    apiHost: normaliseHostUrl(apiHost, environment),
  };
  for (const [key, value] of Object.entries(normalised)) {
    if (value instanceof WidgetSDKError) {
      return createSDKError(value.code, "configuration", { safeMetadata: { host: key } });
    }
  }
  return Object.freeze({
    environment,
    sdkHost: normalised.sdkHost as string,
    iframeHost: normalised.iframeHost as string,
    apiHost: normalised.apiHost as string,
  });
}

export function normaliseHostUrl(value: string, environment: WidgetEnvironment): string | WidgetSDKError {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch (cause) {
    return createSDKError("insecure_host", "configuration", { cause });
  }
  if (parsed.username || parsed.password) {
    return createSDKError("insecure_host", "configuration");
  }
  if (environment !== "development" && parsed.protocol !== "https:") {
    return createSDKError("insecure_host", "configuration");
  }
  if (!['https:', 'http:'].includes(parsed.protocol)) {
    return createSDKError("insecure_host", "configuration");
  }
  if (environment === "development" && parsed.protocol === "http:" && !isLocalDevelopmentHost(parsed.hostname)) {
    return createSDKError("insecure_host", "configuration");
  }
  parsed.hash = "";
  parsed.search = "";
  return parsed.toString().replace(/\/$/, "");
}

function isLocalDevelopmentHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}