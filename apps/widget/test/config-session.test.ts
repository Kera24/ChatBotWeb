import { describe, expect, it, vi } from "vitest";
import { WidgetConfigCache } from "../src/api/config";
import { PublicWidgetApiClient } from "../src/api/client";
import { WidgetBootstrapService } from "../src/services/bootstrap-service";
import { BrowserSessionStore } from "../src/storage/browser-session-store";
import { MemorySessionStore } from "../src/storage/memory-session-store";
import { WidgetStateStore } from "../src/state/widget-state";
import { validConfig, validSession, jsonResponse } from "./fixtures";

const payload = {
  widgetKey: "wpk_dev_1234567890abcdef",
  parentOrigin: "http://localhost:3000",
  sdkVersion: "0.1.0-foundation.0",
  protocolVersion: 1,
  environment: "development" as const,
  initialOpen: false,
  mountMode: "floating" as const,
  debug: false,
};

describe("config cache and session storage", () => {
  it("loads config, stores ETag, and creates no session during bootstrap", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toContain("/config");
      return jsonResponse(validConfig, { headers: { ETag: '"cfg-3"' } });
    });
    const runtime = await new WidgetBootstrapService().bootstrap({ payload, windowRef: window, fetchImpl });
    expect(runtime.stateStore.snapshot().config.status).toBe("ready");
    expect(runtime.stateStore.snapshot().session.status).toBe("none");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("uses validated cached config for 304 and clears corrupted cache", async () => {
    const cache = new WidgetConfigCache(window.sessionStorage, { widgetKey: payload.widgetKey, environment: payload.environment });
    cache.set(validConfig, '"cfg-3"');
    const fetchImpl = vi.fn(async () => new Response(null, { status: 304 }));
    const runtime = await new WidgetBootstrapService().bootstrap({ payload, windowRef: window, fetchImpl });
    expect(runtime.stateStore.snapshot().config.data?.configuration_version).toBe(3);
    window.sessionStorage.setItem(`yoranix:widget-config:${payload.environment}:${payload.widgetKey}`, "not-json");
    expect(cache.get()).toBeNull();
  });

  it("stores sessions in iframe sessionStorage or memory fallback without public state token", async () => {
    const browserStore = new BrowserSessionStore(window.sessionStorage, { widgetKey: payload.widgetKey, environment: payload.environment });
    browserStore.set({
      sessionToken: validSession.session_token,
      expiresAt: validSession.expires_at,
      absoluteExpiresAt: validSession.absolute_expires_at,
      remainingMessages: validSession.remaining_messages,
      configurationVersion: validSession.configuration_version,
      createdAt: "2026-07-16T00:00:00.000Z",
      schemaVersion: "1.0",
    });
    expect(browserStore.get()?.sessionToken).toBe(validSession.session_token);

    const memoryStore = new MemorySessionStore({ widgetKey: payload.widgetKey, environment: payload.environment });
    expect(memoryStore.isAvailable()).toBe(true);
    const stateStore = new WidgetStateStore();
    const client = new PublicWidgetApiClient({ apiBaseUrl: "http://localhost:8000", widgetKey: payload.widgetKey, fetchImpl: async () => jsonResponse(validSession) });
    const runtime = await import("../src/services/session-service");
    const service = new runtime.SessionService({ apiClient: client, sessionStore: memoryStore, stateStore, configurationVersion: 3 });
    await service.ensureSession();
    expect(JSON.stringify(stateStore.snapshot())).not.toContain(validSession.session_token);
  });
});