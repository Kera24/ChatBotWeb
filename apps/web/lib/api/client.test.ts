import { describe, expect, it, vi } from "vitest";

import { dashboardApiGet, getDashboardApiBaseUrl } from "./client";
import { DashboardApiError } from "./errors";
import type { DevelopmentDashboardSession } from "../auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "viewer@example.test",
  role: "viewer",
};

function okResponse(data: unknown = { ok: true }) {
  return new Response(JSON.stringify({ success: true, data }), { status: 200 });
}

function fetchMock() {
  const mock = vi.fn();
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("dashboard API client", () => {
  it("resolves the configured base URL without trailing slash", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local/");

    expect(getDashboardApiBaseUrl()).toBe("http://api.local");
  });

  it("falls back to the local API base URL", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");

    expect(getDashboardApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("adds dashboard development auth headers in the centralized client", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
    const mock = fetchMock().mockResolvedValue(okResponse());

    await dashboardApiGet({ path: "/api/test", session });

    const [, init] = mock.mock.calls[0];
    expect(init.headers).toMatchObject({
      Accept: "application/json",
      "X-Development-User-Email": "viewer@example.test",
      "X-Development-Role": "viewer",
    });
  });

  it.each([
    [401, "unauthorized"],
    [403, "forbidden"],
    [404, "not_found"],
    [409, "conflict"],
    [422, "validation"],
  ] as const)("maps %s responses to %s errors", async (status, kind) => {
    const mock = fetchMock().mockResolvedValue(new Response(JSON.stringify({ detail: "blocked" }), { status }));

    await expect(dashboardApiGet({ path: "/api/test", session })).rejects.toMatchObject({
      name: "DashboardApiError",
      kind,
      status,
    });
    expect(mock).toHaveBeenCalledTimes(1);
  });

  it("maps network failures to a retryable network error", async () => {
    fetchMock().mockRejectedValue(new TypeError("connection refused"));

    await expect(dashboardApiGet({ path: "/api/test", session })).rejects.toBeInstanceOf(DashboardApiError);
    await expect(dashboardApiGet({ path: "/api/test", session })).rejects.toMatchObject({ kind: "network" });
  });
});
