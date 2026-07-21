import type { ValidatedWidgetSDKConfig } from "./config";
import { createSDKError, WidgetSDKError } from "./errors";
import { WIDGET_PROTOCOL_VERSION } from "./protocol";

export type BuiltIframeUrl = Readonly<{
  url: string;
  iframeOrigin: string;
  parentOrigin: string;
}>;

export const RECOMMENDED_IFRAME_ATTRIBUTES = Object.freeze({
  sandbox: "allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox",
  allow: "",
  referrerPolicy: "strict-origin-when-cross-origin",
  title: "Yoranix chat widget",
  loading: "lazy",
});

export function buildWidgetIframeUrl(
  config: ValidatedWidgetSDKConfig,
  parentOrigin = getCurrentParentOrigin(),
): BuiltIframeUrl | WidgetSDKError {
  const normalisedParentOrigin = normaliseOrigin(parentOrigin, config.environment);
  if (normalisedParentOrigin instanceof WidgetSDKError) {
    return normalisedParentOrigin;
  }
  const base = new URL(config.hosts.iframeHost);
  if (config.environment !== "development" && base.protocol !== "https:") {
    return createSDKError("insecure_host", "iframe");
  }
  base.pathname = `/embed/${encodeURIComponent(config.widgetKey)}`;
  base.search = "";
  base.searchParams.set("parent_origin", normalisedParentOrigin);
  base.searchParams.set("protocol", String(WIDGET_PROTOCOL_VERSION));
  base.searchParams.set("sdk", "v1");
  return Object.freeze({
    url: base.toString(),
    iframeOrigin: base.origin,
    parentOrigin: normalisedParentOrigin,
  });
}

export function normaliseOrigin(value: string, environment: ValidatedWidgetSDKConfig["environment"]): string | WidgetSDKError {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch (cause) {
    return createSDKError("invalid_configuration", "iframe", { cause, safeMetadata: { field: "parentOrigin" } });
  }
  if (parsed.origin === "null" || parsed.username || parsed.password || parsed.pathname !== "/" || parsed.search || parsed.hash) {
    return createSDKError("invalid_configuration", "iframe", { safeMetadata: { field: "parentOrigin" } });
  }
  if (!["https:", "http:"].includes(parsed.protocol)) {
    return createSDKError("invalid_configuration", "iframe", { safeMetadata: { field: "parentOrigin" } });
  }
  if (environment !== "development" && parsed.protocol !== "https:") {
    return createSDKError("insecure_host", "iframe", { safeMetadata: { field: "parentOrigin" } });
  }
  if (environment === "development" && parsed.protocol === "http:" && !isLocalDevelopmentHost(parsed.hostname)) {
    return createSDKError("insecure_host", "iframe", { safeMetadata: { field: "parentOrigin" } });
  }
  return parsed.origin;
}

function getCurrentParentOrigin(): string {
  if (typeof window === "undefined" || !window.location?.origin) {
    return "http://localhost";
  }
  return window.location.origin;
}

function isLocalDevelopmentHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}
