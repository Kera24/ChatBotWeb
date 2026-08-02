import { describe, expect, it } from "vitest";

import { developmentDashboardHeaders, getDevelopmentDashboardSession, dashboardSessionFromAuthContext } from "./development-session";

describe("dashboard auth session compatibility", () => {
  it("does not resolve dashboard sessions from NEXT_PUBLIC development variables", () => {
    const result = getDevelopmentDashboardSession();

    expect(result.configured).toBe(false);
    if (!result.configured) {
      expect(result.missing).toEqual([]);
      expect(result.invalid).toEqual([]);
    }
  });

  it("does not emit development authentication headers", () => {
    expect(developmentDashboardHeaders()).toEqual({});
  });

  it("maps authenticated API context into the dashboard session shape", () => {
    const session = dashboardSessionFromAuthContext({
      user: { id: "user-1", email: "owner@example.test", full_name: "Owner", status: "active", email_verified: false, onboarding_complete: true },
      organisation: { name: "Acme", slug: "acme", plan_key: "starter", status: "active" },
      workspace: { name: "Default workspace", slug: "default", status: "active" },
      membership: { role: "org_owner", status: "active" },
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      role: "org_owner",
      onboarding_complete: true,
    });

    expect(session).toMatchObject({ organisationId: "org-1", workspaceId: "workspace-1", userEmail: "owner@example.test", role: "org_owner", onboardingComplete: true });
  });
});
