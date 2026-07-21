import type { PublicMessageResponse } from "../api/contracts";
import type { PublicWidgetApiClient } from "../api/client";
import { DEFAULT_RETRY_POLICY, delay, type RetryPolicy } from "../api/retry";
import { WidgetApiError, toWidgetApiError } from "../api/errors";
import type { WidgetStateStore } from "../state/widget-state";
import type { SessionService } from "./session-service";

export type MessageMetadataValue = string | number | boolean | null;
export type MessageMetadata = Record<string, MessageMetadataValue>;

export type MessageServiceOptions = Readonly<{
  apiClient: PublicWidgetApiClient;
  sessionService: SessionService;
  stateStore: WidgetStateStore;
  retryPolicy?: RetryPolicy;
  idempotencyKeyFactory?: () => string;
}>;

export class MessageService {
  private readonly retryPolicy: RetryPolicy;
  private readonly idempotencyKeyFactory: () => string;

  constructor(private readonly options: MessageServiceOptions) {
    this.retryPolicy = options.retryPolicy ?? DEFAULT_RETRY_POLICY;
    this.idempotencyKeyFactory = options.idempotencyKeyFactory ?? createIdempotencyKey;
  }

  async sendMessage(message: string, metadata: MessageMetadata = {}, existingIdempotencyKey?: string): Promise<PublicMessageResponse> {
    const canonicalMessage = validateLocalMessage(message);
    const safeMetadata = validateMetadata(metadata);
    const idempotencyKey = existingIdempotencyKey ?? this.idempotencyKeyFactory();
    const session = await this.options.sessionService.ensureSession();
    this.options.stateStore.update({ message: { status: "sending" } });
    for (let attempt = 1; attempt <= this.retryPolicy.maxAttempts; attempt += 1) {
      try {
        const response = await this.options.apiClient.sendMessage({
          sessionToken: session.sessionToken,
          message: canonicalMessage,
          metadata: safeMetadata,
          idempotencyKey,
        });
        this.options.sessionService.updateFromMessage(response.remaining_messages, response.session_expires_at);
        this.options.stateStore.update({ message: { status: "sent", lastResponse: response } });
        return response;
      } catch (error) {
        const safe = toWidgetApiError(error, "message");
        if (["invalid_session", "session_expired"].includes(safe.code)) {
          this.options.sessionService.clear(safe.code === "session_expired" ? "expired" : "invalid");
        }
        if (safe.code === "request_in_progress") {
          this.options.stateStore.update({ message: { status: "request_in_progress" }, lastError: safe.toSafeShape() });
        }
        const canRetry = safe.retryable && ["network_error", "request_timeout", "temporarily_unavailable", "request_in_progress"].includes(safe.code) && attempt < this.retryPolicy.maxAttempts;
        if (!canRetry) {
          this.options.stateStore.update({ message: { status: "failed" }, lastError: safe.toSafeShape() });
          throw safe;
        }
        await delay(this.retryPolicy.baseDelayMs * attempt);
      }
    }
    throw new WidgetApiError("safe_internal_error", "message", { retryable: false });
  }
}

export function createIdempotencyKey(cryptoRef: Crypto | undefined = globalThis.crypto): string {
  if (!cryptoRef) {
    throw new WidgetApiError("secure_random_unavailable", "message", { retryable: false });
  }
  if (typeof cryptoRef.randomUUID === "function") {
    return `wid_${cryptoRef.randomUUID()}`;
  }
  if (typeof cryptoRef.getRandomValues === "function") {
    const bytes = new Uint8Array(24);
    cryptoRef.getRandomValues(bytes);
    const token = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    return `wid_${token}`;
  }
  throw new WidgetApiError("secure_random_unavailable", "message", { retryable: false });
}

function validateLocalMessage(message: string): string {
  if (typeof message !== "string") throw new WidgetApiError("message_rejected", "message", { retryable: false });
  const canonical = message.replace(/\r\n?/g, "\n").trim();
  const bytes = new TextEncoder().encode(canonical).length;
  if (!canonical || canonical.length > 4000 || bytes > 12000 || canonical.includes("\0")) {
    throw new WidgetApiError(bytes > 12000 || canonical.length > 4000 ? "session_limit_reached" : "message_rejected", "message", { retryable: false });
  }
  return canonical;
}

function validateMetadata(metadata: MessageMetadata): MessageMetadata {
  const entries = Object.entries(metadata);
  if (entries.length > 10) throw new WidgetApiError("message_rejected", "message", { retryable: false });
  const forbidden = new Set(["organisation_id", "organization_id", "workspace_id", "credential_id", "conversation_id", "model", "provider", "prompt", "session_token", "email", "phone", "origin", "ip"]);
  const output: MessageMetadata = {};
  for (const [key, value] of entries) {
    if (key.length > 60 || forbidden.has(key)) throw new WidgetApiError("message_rejected", "message", { retryable: false });
    if (typeof value === "string" && value.length > 250) throw new WidgetApiError("message_rejected", "message", { retryable: false });
    if (!["string", "number", "boolean"].includes(typeof value) && value !== null) throw new WidgetApiError("message_rejected", "message", { retryable: false });
    output[key] = value;
  }
  return output;
}