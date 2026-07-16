import { createSafeProtocolError } from "@yoranix/widget-sdk";
import { MAX_PARENT_ORIGIN_LENGTH } from "./constants";
import { IframeShellError } from "./errors";

export type ParentOriginResolution = Readonly<{
  parentOrigin: string;
  referrerOrigin?: string;
}>;

export function resolveParentOriginFromBootstrap(
  locationHref: string,
  referrer: string,
  options: { requireHttpsParent?: boolean } = {},
): ParentOriginResolution {
  const current = new URL(locationHref);
  const requested = current.searchParams.get("parent_origin");
  if (!requested || requested.length > MAX_PARENT_ORIGIN_LENGTH) {
    throw new IframeShellError(createSafeProtocolError("invalid_parent_origin", "bootstrap"));
  }
  const parentOrigin = normaliseOrigin(requested, options.requireHttpsParent ?? current.protocol === "https:");
  const referrerOrigin = referrer ? normaliseReferrerOrigin(referrer) : undefined;
  if (referrerOrigin && referrerOrigin !== parentOrigin) {
    throw new IframeShellError(createSafeProtocolError("origin_mismatch", "bootstrap"));
  }
  return Object.freeze({ parentOrigin, ...(referrerOrigin ? { referrerOrigin } : {}) });
}

export function normaliseOrigin(value: string, requireHttps: boolean): string {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new IframeShellError(createSafeProtocolError("invalid_parent_origin", "bootstrap"));
  }
  if (parsed.origin === "null" || parsed.username || parsed.password || parsed.pathname !== "/" || parsed.search || parsed.hash) {
    throw new IframeShellError(createSafeProtocolError("invalid_parent_origin", "bootstrap"));
  }
  if (!["https:", "http:"].includes(parsed.protocol)) {
    throw new IframeShellError(createSafeProtocolError("invalid_parent_origin", "bootstrap"));
  }
  if (requireHttps && parsed.protocol !== "https:" && !isLocalhost(parsed.hostname)) {
    throw new IframeShellError(createSafeProtocolError("invalid_parent_origin", "bootstrap"));
  }
  return parsed.origin;
}

function normaliseReferrerOrigin(referrer: string): string {
  let parsed: URL;
  try {
    parsed = new URL(referrer);
  } catch {
    throw new IframeShellError(createSafeProtocolError("invalid_parent_origin", "bootstrap"));
  }
  return parsed.origin;
}

function isLocalhost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}
