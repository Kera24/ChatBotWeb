import { describe, expect, it, vi } from "vitest";

import { getConversationDetail, listConversations } from "./conversations";
import type { DevelopmentDashboardSession } from "../auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-abc",
  workspaceId: "workspace-def",
  userEmail: "admin@example.test",
  role: "client_admin",
};

function mockFetch() {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: [], meta: {} }), { status: 200 }));
  vi.stubGlobal("fetch", mock);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
  return mock;
}

describe("conversation API helpers", () => {
  it("includes tenant ids, filters, limit, and offset when listing conversations", async () => {
    const mock = mockFetch();

    await listConversations(session, { status: "active", channel: "dashboard_test", limit: 10, offset: 20 });

    const url = new URL(String(mock.mock.calls[0][0]));
    expect(url.pathname).toBe("/api/v1/workspaces/workspace-def/conversations");
    expect(url.searchParams.get("organisation_id")).toBe("org-abc");
    expect(url.searchParams.get("status")).toBe("active");
    expect(url.searchParams.get("channel")).toBe("dashboard_test");
    expect(url.searchParams.get("limit")).toBe("10");
    expect(url.searchParams.get("offset")).toBe("20");
  });

  it("includes tenant scope when loading conversation detail", async () => {
    const mock = mockFetch();

    await getConversationDetail(session, "conversation-123");

    const url = new URL(String(mock.mock.calls[0][0]));
    expect(url.pathname).toBe("/api/v1/workspaces/workspace-def/conversations/conversation-123");
    expect(url.searchParams.get("organisation_id")).toBe("org-abc");
  });
});
