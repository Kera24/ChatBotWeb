import { describe, expect, it, vi } from "vitest";

import { listMemberships, updateMembershipRole, updateMembershipStatus } from "./users";
import type { DevelopmentDashboardSession } from "../auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

function mockFetch(data: unknown = [], meta: Record<string, unknown> = {}) {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data, meta }), { status: 200 }));
  vi.stubGlobal("fetch", mock);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
  return mock;
}

describe("users API helpers", () => {
  it("lists memberships with tenant scope", async () => {
    const mock = mockFetch([], { roles: ["viewer"], statuses: ["active"] });

    await listMemberships(session);

    const [url, init] = mock.mock.calls[0];
    const parsed = new URL(String(url));
    expect(parsed.pathname).toBe("/api/v1/workspaces/workspace-1/memberships");
    expect(parsed.searchParams.get("organisation_id")).toBe("org-1");
    expect(init.headers).not.toHaveProperty("X-Development-User-Email");
    expect(init.credentials).toBe("include");
  });

  it("patches membership role through the authenticated dashboard client", async () => {
    const mock = mockFetch({ id: "membership-1", role: "viewer" });

    await updateMembershipRole(session, "membership-1", "viewer");

    const [url, init] = mock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/workspaces/workspace-1/memberships/membership-1/role");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ role: "viewer" });
  });

  it("patches membership status without exposing other tenant ids", async () => {
    const mock = mockFetch({ id: "membership-1", status: "inactive" });

    await updateMembershipStatus(session, "membership-1", "inactive");

    const [url, init] = mock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/workspaces/workspace-1/memberships/membership-1/status");
    expect(JSON.parse(String(init.body))).toEqual({ status: "inactive" });
  });
});
