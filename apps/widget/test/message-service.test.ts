import { describe, expect, it, vi } from "vitest";
import { PublicWidgetApiClient } from "../src/api/client";
import { MessageService, createIdempotencyKey } from "../src/services/message-service";
import { SessionService } from "../src/services/session-service";
import { MemorySessionStore } from "../src/storage/memory-session-store";
import { WidgetStateStore } from "../src/state/widget-state";
import { validMessage, validSession, jsonResponse } from "./fixtures";

function makeServices(fetchImpl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  const apiClient = new PublicWidgetApiClient({ apiBaseUrl: "http://localhost:8000", widgetKey: "wpk_dev_123", fetchImpl });
  const stateStore = new WidgetStateStore();
  const sessionService = new SessionService({
    apiClient,
    sessionStore: new MemorySessionStore({ widgetKey: "wpk_dev_123", environment: "development" }),
    stateStore,
    configurationVersion: 3,
  });
  return { apiClient, stateStore, sessionService };
}

describe("message service", () => {
  it("creates a session lazily, sends with idempotency key, and updates safe state", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const { stateStore, sessionService, apiClient } = makeServices(async (input, init) => {
      calls.push({ input, init });
      return String(input).endsWith("/sessions") ? jsonResponse(validSession) : jsonResponse(validMessage);
    });
    const service = new MessageService({ apiClient, sessionService, stateStore, idempotencyKeyFactory: () => "wid_fixed_key_123456789" });

    const response = await service.sendMessage("  Hello\r\nthere  ");

    expect(response.answer).toBe("Safe answer");
    expect(calls[0]?.input).toContain("/sessions");
    expect(calls[1]?.input).toContain("/messages");
    expect((calls[1]?.init?.headers as Headers).get("Idempotency-Key")).toBe("wid_fixed_key_123456789");
    expect(calls[1]?.init?.body).toContain("Hello\\nthere");
    expect(JSON.stringify(stateStore.snapshot())).not.toContain(validSession.session_token);
  });

  it("reuses the same idempotency key across retry attempts", async () => {
    const keys: string[] = [];
    let messageAttempts = 0;
    const { stateStore, sessionService, apiClient } = makeServices(async (input, init) => {
      if (String(input).endsWith("/sessions")) return jsonResponse(validSession);
      messageAttempts += 1;
      keys.push((init?.headers as Headers).get("Idempotency-Key") ?? "");
      if (messageAttempts === 1) throw new TypeError("network down");
      return jsonResponse(validMessage);
    });
    const service = new MessageService({
      apiClient,
      sessionService,
      stateStore,
      idempotencyKeyFactory: () => "wid_retry_key_123456789",
      retryPolicy: { maxAttempts: 2, baseDelayMs: 0 },
    });

    await service.sendMessage("hello");
    expect(keys).toEqual(["wid_retry_key_123456789", "wid_retry_key_123456789"]);
  });

  it("clears stored token after invalid session and does not auto-resend with a new token", async () => {
    let sessionCalls = 0;
    const { stateStore, sessionService, apiClient } = makeServices(async (input) => {
      if (String(input).endsWith("/sessions")) {
        sessionCalls += 1;
        return jsonResponse(validSession);
      }
      return jsonResponse({ code: "invalid_session", message: "invalid", retryable: false }, { status: 404 });
    });
    const service = new MessageService({ apiClient, sessionService, stateStore, idempotencyKeyFactory: () => "wid_invalid_key_123456789" });

    await expect(service.sendMessage("hello")).rejects.toMatchObject({ code: "invalid_session" });
    expect(sessionCalls).toBe(1);
    expect(stateStore.snapshot().session.status).toBe("invalid");
  });

  it("fails safely without weak random idempotency", () => {
    expect(() => createIdempotencyKey({} as Crypto)).toThrow();
  });
});