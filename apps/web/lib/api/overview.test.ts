import { describe, expect, it, vi } from "vitest";

import { loadOverviewData } from "./overview";
import { listConversations } from "./conversations";
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

function envelope<T>(data: T, meta: Record<string, unknown> = {}) {
  return { success: true, data, meta };
}

describe("overview API aggregation", () => {
  it("loads tenant-scoped overview sources through existing clients", async () => {
    vi.mocked(listDocuments).mockResolvedValue(envelope([{ id: "doc-1" }] as never));
    vi.mocked(listConversations).mockResolvedValue(envelope([{ id: "conversation-1" }] as never));
    vi.mocked(listWidgets).mockResolvedValue(envelope([{ id: "widget-1" }] as never));
    vi.mocked(listUnansweredReviewItems).mockResolvedValue(envelope([{ assistant_message_id: "message-1" }] as never, { total: 7 }));

    const data = await loadOverviewData(session);

    expect(listDocuments).toHaveBeenCalledWith(session, "widget-1");
    expect(listConversations).toHaveBeenCalledWith(session, { assistantId: "widget-1", limit: 50, offset: 0 });
    expect(listWidgets).toHaveBeenCalledWith(session);
    expect(listUnansweredReviewItems).toHaveBeenCalledWith(session, { assistantId: "widget-1", review_status: "open", limit: 20, offset: 0 });
    expect(data.reviewTotal).toBe(7);
    expect(data.documents).toHaveLength(1);
    expect(data.conversations).toHaveLength(1);
    expect(data.widgets).toHaveLength(1);
    expect(data.reviewItems).toHaveLength(1);
  });

  it("falls back to the visible review count when the backend omits total", async () => {
    vi.mocked(listDocuments).mockResolvedValue(envelope([]));
    vi.mocked(listConversations).mockResolvedValue(envelope([]));
    vi.mocked(listWidgets).mockResolvedValue(envelope([]));
    vi.mocked(listUnansweredReviewItems).mockResolvedValue(envelope([{ assistant_message_id: "message-1" }, { assistant_message_id: "message-2" }] as never));

    const data = await loadOverviewData(session);

    expect(data.reviewTotal).toBe(2);
  });
});
