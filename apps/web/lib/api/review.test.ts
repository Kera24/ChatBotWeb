import { describe, expect, it, vi } from "vitest";

import { getUnansweredReviewItem, listUnansweredReviewItems, updateUnansweredReviewStatus } from "./review";
import type { DevelopmentDashboardSession } from "../auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

function mockFetch(data: unknown = []) {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data, meta: { total: 0, count: 0, limit: 20, offset: 0 } }), { status: 200 }));
  vi.stubGlobal("fetch", mock);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
  return mock;
}

describe("review API helpers", () => {
  it("serializes tenant scope, filters, and pagination", async () => {
    const mock = mockFetch();

    await listUnansweredReviewItems(session, {
      answer_state: "fallback",
      review_status: "open",
      channel: "dashboard_test",
      created_after: "2026-07-01",
      created_before: "2026-07-13",
      limit: 10,
      offset: 20,
    });

    const url = new URL(String(mock.mock.calls[0][0]));
    expect(url.pathname).toBe("/api/v1/workspaces/workspace-1/review/unanswered");
    expect(url.searchParams.get("organisation_id")).toBe("org-1");
    expect(url.searchParams.get("answer_state")).toBe("fallback");
    expect(url.searchParams.get("review_status")).toBe("open");
    expect(url.searchParams.get("channel")).toBe("dashboard_test");
    expect(url.searchParams.get("limit")).toBe("10");
    expect(url.searchParams.get("offset")).toBe("20");
  });

  it("loads detail with tenant scope", async () => {
    const mock = mockFetch({ item: {}, conversation_context: [] });

    await getUnansweredReviewItem(session, "message-1");

    const url = new URL(String(mock.mock.calls[0][0]));
    expect(url.pathname).toBe("/api/v1/workspaces/workspace-1/review/unanswered/message-1");
    expect(url.searchParams.get("organisation_id")).toBe("org-1");
  });

  it("patches review status through the centralized dashboard client", async () => {
    const mock = mockFetch({ review_status: "reviewed" });

    await updateUnansweredReviewStatus(session, "message-1", { review_status: "reviewed", reviewer_note: "Checked" });

    const [url, init] = mock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/workspaces/workspace-1/review/unanswered/message-1");
    expect(init.method).toBe("PATCH");
    expect(init.headers).toMatchObject({ "X-Development-User-Email": "admin@example.test", "X-Development-Role": "client_admin" });
    expect(JSON.parse(String(init.body))).toEqual({ review_status: "reviewed", reviewer_note: "Checked" });
  });
});
