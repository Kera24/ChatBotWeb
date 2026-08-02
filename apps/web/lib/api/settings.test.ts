import { describe, expect, it, vi } from "vitest";

import { getWorkspaceSettings, updateWorkspaceSettings } from "./settings";
import type { DevelopmentDashboardSession } from "../auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

function mockFetch(data: unknown = {}) {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data, meta: {} }), { status: 200 }));
  vi.stubGlobal("fetch", mock);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
  return mock;
}

describe("settings API helpers", () => {
  it("loads workspace settings with tenant scope", async () => {
    const mock = mockFetch({ workspace: { id: "workspace-1" } });

    await getWorkspaceSettings(session);

    const [url, init] = mock.mock.calls[0];
    const parsed = new URL(String(url));
    expect(parsed.pathname).toBe("/api/v1/workspaces/workspace-1/settings");
    expect(parsed.searchParams.get("organisation_id")).toBe("org-1");
    expect(init.headers).not.toHaveProperty("X-Development-User-Email");
    expect(init.credentials).toBe("include");
  });

  it("updates only supported workspace settings", async () => {
    const mock = mockFetch({ workspace: { id: "workspace-1" } });

    await updateWorkspaceSettings(session, { name: "Support Workspace", default_language: "en-AU", expected_updated_at: "2026-08-01T00:00:00Z" });

    const [url, init] = mock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/workspaces/workspace-1/settings");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ name: "Support Workspace", default_language: "en-AU", expected_updated_at: "2026-08-01T00:00:00Z" });
  });
});
