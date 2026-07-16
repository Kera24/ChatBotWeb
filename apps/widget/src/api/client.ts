import type { PublicMessageResponse, PublicSessionResponse, PublicWidgetConfigResponse, SafeErrorResponse } from "./contracts";
import { WidgetApiError, type WidgetApiPhase } from "./errors";
import { getHeaders, jsonHeaders } from "./headers";
import { validateConfigResponse, validateMessageResponse, validateSessionResponse } from "../security/public-response-validation";

export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export type PublicWidgetApiClientOptions = Readonly<{
  apiBaseUrl: string;
  widgetKey: string;
  fetchImpl?: FetchLike;
  timeoutMs?: number;
  maxResponseBytes?: number;
}>;

export type ConfigResult =
  | Readonly<{ status: 200; config: PublicWidgetConfigResponse; etag: string | null }>
  | Readonly<{ status: 304 }>;

export class PublicWidgetApiClient {
  private readonly fetchImpl: FetchLike;
  private readonly timeoutMs: number;
  private readonly maxResponseBytes: number;
  private readonly base: string;
  private readonly widgetKey: string;

  constructor(options: PublicWidgetApiClientOptions) {
    this.fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);
    this.timeoutMs = options.timeoutMs ?? 8000;
    this.maxResponseBytes = options.maxResponseBytes ?? 256_000;
    this.base = options.apiBaseUrl.replace(/\/$/, "");
    this.widgetKey = encodeURIComponent(options.widgetKey);
  }

  async getConfig(etag?: string | null): Promise<ConfigResult> {
    const response = await this.request("configuration", `/api/v1/widget/${this.widgetKey}/config`, {
      method: "GET",
      headers: getHeaders(etag),
    });
    if (response.status === 304) {
      return Object.freeze({ status: 304 as const });
    }
    const json = await this.readJson(response, "configuration");
    return Object.freeze({ status: 200 as const, config: validateConfigResponse(json), etag: response.headers.get("ETag") });
  }

  async createSession(): Promise<PublicSessionResponse> {
    const response = await this.request("session", `/api/v1/widget/${this.widgetKey}/sessions`, {
      method: "POST",
      headers: jsonHeaders(),
      body: "{}",
    });
    return validateSessionResponse(await this.readJson(response, "session"));
  }

  async sendMessage(input: { sessionToken: string; message: string; metadata?: Record<string, string | number | boolean | null>; idempotencyKey: string }): Promise<PublicMessageResponse> {
    const response = await this.request("message", `/api/v1/widget/${this.widgetKey}/messages`, {
      method: "POST",
      headers: jsonHeaders({ "Idempotency-Key": input.idempotencyKey }),
      body: JSON.stringify({
        session_token: input.sessionToken,
        message: input.message,
        metadata: input.metadata ?? {},
      }),
    });
    return validateMessageResponse(await this.readJson(response, "message"));
  }

  private async request(phase: WidgetApiPhase, path: string, init: RequestInit): Promise<Response> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(new WidgetApiError("request_timeout", phase)), this.timeoutMs);
    try {
      const response = await this.fetchImpl(`${this.base}${path}`, {
        ...init,
        credentials: "omit",
        signal: controller.signal,
      });
      if (!response.ok && response.status !== 304) {
        throw await this.mapErrorResponse(response, phase);
      }
      return response;
    } catch (error) {
      if (error instanceof WidgetApiError) throw error;
      if (controller.signal.aborted) {
        throw new WidgetApiError("request_timeout", phase);
      }
      throw new WidgetApiError("network_error", phase);
    } finally {
      clearTimeout(timeout);
    }
  }

  private async readJson(response: Response, phase: WidgetApiPhase): Promise<unknown> {
    const contentType = response.headers.get("Content-Type") ?? "";
    if (!contentType.toLowerCase().includes("application/json")) {
      throw new WidgetApiError("incompatible_response", phase, { retryable: false });
    }
    const text = await response.text();
    if (text.length > this.maxResponseBytes) {
      throw new WidgetApiError("incompatible_response", phase, { retryable: false });
    }
    try {
      return JSON.parse(text);
    } catch {
      throw new WidgetApiError("incompatible_response", phase, { retryable: false });
    }
  }

  private async mapErrorResponse(response: Response, phase: WidgetApiPhase): Promise<WidgetApiError> {
    const retryAfter = parseRetryAfter(response.headers.get("Retry-After"));
    let body: SafeErrorResponse | null = null;
    try {
      if ((response.headers.get("Content-Type") ?? "").toLowerCase().includes("application/json")) {
        body = JSON.parse(await response.text()) as SafeErrorResponse;
      }
    } catch {
      body = null;
    }
    const code = mapSafeCode(body?.code, response.status, phase);
    return new WidgetApiError(code, phase, {
      retryable: body?.retryable ?? (response.status >= 500 || response.status === 429),
      requestId: body?.request_id,
      retryAfterSeconds: body?.retry_after_seconds ?? retryAfter,
    });
  }
}

function parseRetryAfter(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number.parseInt(value, 10);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined;
}

function mapSafeCode(code: string | undefined, status: number, phase: WidgetApiPhase): WidgetApiError["code"] {
  if (code === "invalid_session" || code === "revoked_session" || code === "blocked_session" || code === "completed_session") return "invalid_session";
  if (code === "expired_session") return "session_expired";
  if (code === "session_limit_reached") return "session_limit_reached";
  if (code === "unsafe_request") return "unsafe_request";
  if (code === "quota_exceeded") return "quota_exceeded";
  if (code === "request_in_progress") return "request_in_progress";
  if (code === "rate_limited" || status === 429) return "rate_limited";
  if (code === "origin_required" || code === "origin_not_allowed" || code === "malformed_origin") return "origin_denied";
  if (code === "invalid_widget" || status === 404) return "invalid_widget";
  if (status === 503) return "temporarily_unavailable";
  if (phase === "session") return "session_creation_failed";
  if (phase === "message") return "message_rejected";
  return "configuration_unavailable";
}
