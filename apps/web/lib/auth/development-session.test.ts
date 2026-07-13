import { describe, expect, it, vi } from "vitest";

import { developmentDashboardHeaders, getDevelopmentDashboardSession } from "./development-session";

function setCompleteEnv() {
  vi.stubEnv("NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID", "org-1");
  vi.stubEnv("NEXT_PUBLIC_DEVELOPMENT_WORKSPACE_ID", "workspace-1");
  vi.stubEnv("NEXT_PUBLIC_DEVELOPMENT_USER_EMAIL", "owner@example.test");
  vi.stubEnv("NEXT_PUBLIC_DEVELOPMENT_ROLE", "org_owner");
}

describe("development dashboard session", () => {
  it("returns a complete development configuration", () => {
    setCompleteEnv();

    const result = getDevelopmentDashboardSession();

    expect(result.configured).toBe(true);
    if (result.configured) {
      expect(result.session).toEqual({
        organisationId: "org-1",
        workspaceId: "workspace-1",
        userEmail: "owner@example.test",
        role: "org_owner",
      });
      expect(developmentDashboardHeaders(result.session)).toEqual({
        "X-Development-User-Email": "owner@example.test",
        "X-Development-Role": "org_owner",
      });
    }
  });

  it.each([
    ["NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID"],
    ["NEXT_PUBLIC_DEVELOPMENT_WORKSPACE_ID"],
    ["NEXT_PUBLIC_DEVELOPMENT_USER_EMAIL"],
    ["NEXT_PUBLIC_DEVELOPMENT_ROLE"],
  ])("reports missing %s without leaking configured values", (missingKey) => {
    setCompleteEnv();
    vi.stubEnv(missingKey, "");

    const result = getDevelopmentDashboardSession();

    expect(result.configured).toBe(false);
    if (!result.configured) {
      expect(result.missing).toContain(missingKey);
      expect(JSON.stringify(result)).not.toContain("owner@example.test");
      expect(JSON.stringify(result)).not.toContain("workspace-1");
    }
  });

  it("reports an invalid role safely", () => {
    setCompleteEnv();
    vi.stubEnv("NEXT_PUBLIC_DEVELOPMENT_ROLE", "admin-but-not-real");

    const result = getDevelopmentDashboardSession();

    expect(result.configured).toBe(false);
    if (!result.configured) {
      expect(result.invalid).toEqual(["NEXT_PUBLIC_DEVELOPMENT_ROLE"]);
      expect(JSON.stringify(result)).not.toContain("admin-but-not-real");
    }
  });
});
