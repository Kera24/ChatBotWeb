import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { OverviewData } from "../../lib/api/overview";
import { buildRecentActivity, RecentActivity } from "./recent-activity";

const baseData: OverviewData = { documents: [], conversations: [], widgets: [], reviewItems: [], reviewTotal: 0 };

describe("buildRecentActivity", () => {
  it("merges documents, conversations, widgets, and review items using only their real timestamps", () => {
    const data: OverviewData = {
      documents: [{ id: "d1", organisation_id: "o", workspace_id: "w", title: "Admissions Policy", source_type: "pdf", source_key: null, status: "ready", category: null, visibility: "workspace", created_by_user_id: null, active_document_version_id: null, metadata_json: null, archived_at: null, expires_at: null, deleted_at: null, created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-05T00:00:00.000Z" }],
      conversations: [{ id: "c1", assistant_id: "assistant-1", organisation_id: "o", workspace_id: "w", channel: "widget", status: "active", title: null, started_at: "2026-01-02T00:00:00.000Z", last_message_at: "2026-01-06T00:00:00.000Z", ended_at: null, message_count: 3, last_message_preview: null, metadata: null }],
      widgets: [],
      reviewItems: [],
      reviewTotal: 0,
    };
    const activity = buildRecentActivity(data);
    expect(activity).toHaveLength(2);
    expect(activity[0].id).toBe("conversation-c1");
    expect(activity[1].id).toBe("document-d1");
  });

  it("caps the merged timeline at 8 items", () => {
    const data: OverviewData = {
      ...baseData,
      documents: Array.from({ length: 12 }, (_, index) => ({ id: `d${index}`, organisation_id: "o", workspace_id: "w", title: `Doc ${index}`, source_type: "pdf", source_key: null, status: "ready", category: null, visibility: "workspace", created_by_user_id: null, active_document_version_id: null, metadata_json: null, archived_at: null, expires_at: null, deleted_at: null, created_at: "2026-01-01T00:00:00.000Z", updated_at: `2026-01-${String(index + 1).padStart(2, "0")}T00:00:00.000Z` })),
    };
    expect(buildRecentActivity(data)).toHaveLength(8);
  });
});

describe("RecentActivity", () => {
  it("renders a timeline with real links and timestamps", () => {
    const items = buildRecentActivity({
      ...baseData,
      conversations: [{ id: "c1", assistant_id: "assistant-1", organisation_id: "o", workspace_id: "w", channel: "widget", status: "active", title: "Fee question", started_at: "2026-01-02T00:00:00.000Z", last_message_at: "2026-01-06T00:00:00.000Z", ended_at: null, message_count: 3, last_message_preview: null, metadata: null }],
    });
    render(<RecentActivity items={items} />);
    expect(screen.getByRole("link", { name: "Fee question" }).getAttribute("href")).toBe("/conversations/c1");
  });

  it("shows an empty state when there is no activity yet", () => {
    render(<RecentActivity items={[]} />);
    expect(screen.getByText("No recent activity")).toBeTruthy();
  });
});
