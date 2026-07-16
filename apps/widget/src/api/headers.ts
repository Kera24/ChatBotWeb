export const JSON_CONTENT_TYPE = "application/json";

export function jsonHeaders(extra: Record<string, string> = {}): Headers {
  const headers = new Headers(extra);
  headers.set("Accept", JSON_CONTENT_TYPE);
  headers.set("Content-Type", JSON_CONTENT_TYPE);
  return headers;
}

export function getHeaders(etag?: string | null): Headers {
  const headers = new Headers({ Accept: JSON_CONTENT_TYPE });
  if (etag) {
    headers.set("If-None-Match", etag);
  }
  return headers;
}
