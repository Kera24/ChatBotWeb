import { beforeEach, describe, expect, it, vi } from "vitest";

import { loadAnalyticsData } from "./analytics";
import { getConversationDetail, listConversations } from "./conversations";
import { listDocuments } from "./documents";
import { listUnansweredReviewItems } from "./review";
import { listWidgets } from "./widgets";
import type { DevelopmentDashboardSession } from "../auth/development-session";

vi.mock("./conversations");
vi.mock("./documents");
vi.mock("./review");
vi.mock("./widgets");

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

beforeEach(() => {
  vi.resetAllMocks();
});

function envelope<T>(data: T, meta: Record<string, unknown> = {}) {
  return { success: true, data, meta };
}

describe("analytics API aggregation", () => {
  it("uses existing tenant-scoped clients and supported backend filters", async () => {
    vi.mocked(listDocuments).mockResolvedValue(envelope([{ id: "doc-ready", status: "ready" }, { id: "doc-failed", status: "failed" }] as never));
    vi.mocked(listConversations).mockResolvedValue(envelope([{ id: "conversation-1" }] as never));
    vi.mocked(getConversationDetail).mockResolvedValue(envelope({ id: "conversation-1", messages: [] } as never));
    vi.mocked(listWidgets).mockResolvedValue(envelope([{ id: "widget-1" }] as never));
    vi.mocked(listUnansweredReviewItems).mockResolvedValue(envelope([{ assistant_message_id: "message-1" }] as never, { total: 4 }));

    const data = await loadAnalyticsData(session, {
      assistantId: "widget-1",
      started_after: "2026-07-01",
      started_before: "2026-07-31",
      conversation_status: "active",
      conversation_channel: "widget",
      document_status: "failed",
    });

    expect(listConversations).toHaveBeenCalledWith(session, {
      assistantId: "widget-1",
      status: "active",
      channel: "widget",
      started_after: "2026-07-01",
      started_before: "2026-07-31",
      limit: 100,
      offset: 0,
    });
    expect(listUnansweredReviewItems).toHaveBeenCalledWith(session, {
      assistantId: "widget-1",
      review_status: "open",
      channel: "widget",
      created_after: "2026-07-01",
      created_before: "2026-07-31",
      limit: 100,
      offset: 0,
    });
    expect(getConversationDetail).toHaveBeenCalledWith(session, "conversation-1", "widget-1");
    expect(data.documents).toEqual([{ id: "doc-failed", status: "failed" }]);
    expect(data.reviewTotal).toBe(4);
  });

  it("limits detailed quality sampling while keeping the recent summary window", async () => {
    const conversations = Array.from({ length: 30 }, (_, index) => ({ id: `conversation-${index}` }));
    vi.mocked(listDocuments).mockResolvedValue(envelope([]));
    vi.mocked(listConversations).mockResolvedValue(envelope(conversations as never));
    vi.mocked(getConversationDetail).mockResolvedValue(envelope({ id: "sample", messages: [] } as never));
    vi.mocked(listWidgets).mockResolvedValue(envelope([]));
    vi.mocked(listUnansweredReviewItems).mockResolvedValue(envelope([]));

    const data = await loadAnalyticsData(session);

    expect(data.conversations).toHaveLength(30);
    expect(getConversationDetail).toHaveBeenCalledTimes(25);
    expect(data.detailSampleLimit).toBe(25);
    expect(data.recentWindowLimit).toBe(100);
  });
});
