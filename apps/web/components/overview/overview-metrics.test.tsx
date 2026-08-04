import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import type { OverviewData } from "../../lib/api/overview";
import type { WidgetDetail } from "../../lib/api/widgets";
import { buildExecutiveMetrics, OverviewMetrics } from "./overview-metrics";

function buildAssistant(overrides: Partial<WidgetDetail> = {}): WidgetDetail {
  return {
    id: "assistant-1",
    display_name: "Admissions Assistant",
    public_identifier: "public-1",
    public_credential_id: "credential-1",
    publication_status: "published",
    active_revision_number: 2,
    active_published_revision_id: "revision-2",
    draft_revision_id: "revision-3",
    draft_dirty: false,
    operational_status: "enabled",
    pilot_status: "approved",
    release_channel: "staging",
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-10T00:00:00.000Z",
    draft: null,
    active_published_revision: null,
    diff: null,
    ...overrides,
  };
}

const data: OverviewData = {
  documents: [
    { id: "d1", organisation_id: "o", workspace_id: "w", title: "Doc A", source_type: "pdf", source_key: null, status: "ready", category: null, visibility: "workspace", created_by_user_id: null, active_document_version_id: null, metadata_json: null, archived_at: null, expires_at: null, deleted_at: null, created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z" },
    { id: "d2", organisation_id: "o", workspace_id: "w", title: "Doc B", source_type: "pdf", source_key: null, status: "failed", category: null, visibility: "workspace", created_by_user_id: null, active_document_version_id: null, metadata_json: null, archived_at: null, expires_at: null, deleted_at: null, created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z" },
  ],
  conversations: [
    { id: "c1", assistant_id: "assistant-1", organisation_id: "o", workspace_id: "w", channel: "widget", status: "active", title: null, started_at: "2026-01-01T00:00:00.000Z", last_message_at: null, ended_at: null, message_count: 1, last_message_preview: null, metadata: null },
  ],
  widgets: [buildAssistant()],
  reviewItems: [],
  reviewTotal: 2,
};

describe("buildExecutiveMetrics", () => {
  it("computes totals from existing fields only and labels the conversation window as bounded", () => {
    const metrics = buildExecutiveMetrics(data, [buildAssistant()], 50);
    const conversations = metrics.find((metric) => metric.key === "conversations");
    expect(conversations?.value).toBe("1");
    expect(conversations?.detail).toMatch(/bounded|recent window of up to 50/i);

    const failed = metrics.find((metric) => metric.key === "failed-documents");
    expect(failed?.value).toBe("1");

    const gaps = metrics.find((metric) => metric.key === "knowledge-gaps");
    expect(gaps?.value).toBe("2");
  });
});

describe("OverviewMetrics", () => {
  it("renders every metric card with label, value, and detail", () => {
    const metrics = buildExecutiveMetrics(data, [buildAssistant()], 50);
    render(<OverviewMetrics metrics={metrics} />);

    const grid = screen.getByLabelText("Executive metrics");
    expect(within(grid).getByText("Total assistants")).toBeTruthy();
    expect(within(grid).getByText("Published assistants")).toBeTruthy();
    expect(within(grid).getAllByText("1/1").length).toBeGreaterThan(0);
  });
});
