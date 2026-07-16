import { describe, expect, it, vi } from "vitest";
import { PublicWidgetApiClient } from "../src/api/client";

import { validConfig, validSession, validMessage, jsonResponse } from "./fixtures";

describe("public widget API client", () => {
  it("calls public endpoints from iframe with safe headers and omitted credentials", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ input, init });
      const url = String(input);
      if (url.endsWith("/config")) return jsonResponse(validConfig, { headers: { ETag: '"cfg-3"' } });
      if (url.endsWith("/sessions")) return jsonResponse(validSession);
      return jsonResponse(validMessage);
    });
    const client = new PublicWidgetApiClient({ apiBaseUrl: "https://api.example", widgetKey: "wpk_dev_123", fetchImpl });

    await client.getConfig('"old"');
    await client.createSession();
    await client.sendMessage({ sessionToken: validSession.session_token, message: "hello", idempotencyKey: "wid_1234567890abcdef" });

    expect(calls[0]?.input).toBe("https://api.example/api/v1/widget/wpk_dev_123/config");
    expect(calls[0]?.init?.credentials).toBe("omit");
    expect((calls[0]?.init?.headers as Headers).get("If-None-Match")).toBe('"old"');
    expect(calls[1]?.input).toBe("https://api.example/api/v1/widget/wpk_dev_123/sessions");
    expect(calls[2]?.input).toBe("https://api.example/api/v1/widget/wpk_dev_123/messages");
    expect((calls[2]?.init?.headers as Headers).get("Idempotency-Key")).toBe("wid_1234567890abcdef");
    expect((calls[2]?.init?.headers as Headers).has("Authorization")).toBe(false);
    expect(String(calls[2]?.input)).not.toContain("organisation_id");
  });

  it("rejects incompatible public responses and maps safe errors", async () => {
    const client = new PublicWidgetApiClient({
      apiBaseUrl: "https://api.example",
      widgetKey: "wpk_dev_123",
      fetchImpl: async () => jsonResponse({ ...validConfig, session_token: validSession.session_token }),
    });
    await expect(client.getConfig()).rejects.toMatchObject({ code: "incompatible_response" });
  });

  it("maps rate limits without exposing backend internals", async () => {
    const client = new PublicWidgetApiClient({
      apiBaseUrl: "https://api.example",
      widgetKey: "wpk_dev_123",
      fetchImpl: async () => jsonResponse({ code: "rate_limited", message: "slow", retryable: true, retry_after_seconds: 4 }, { status: 429 }),
    });
    await expect(client.createSession()).rejects.toMatchObject({ code: "rate_limited", retryAfterSeconds: 4 });
  });
});
