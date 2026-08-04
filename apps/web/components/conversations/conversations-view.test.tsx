import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { ConversationSummary } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { ConversationsView } from "./conversations-view";

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

const conversation: ConversationSummary = {
  id: "conversation-12345678",
  assistant_id: "assistant-1",
  organisation_id: "org-1",
  workspace_id: "workspace-1",
  channel: "widget",
  status: "active",
  title: "Pricing question",
  started_at: "2026-07-12T01:00:00.000Z",
  last_message_at: "2026-07-12T01:03:00.000Z",
  ended_at: null,
  message_count: 2,
  last_message_preview: "Preview text.",
  metadata: null,
};

describe("ConversationsView", () => {
  it("renders the header, filters, inbox, and pagination when conversations are present", () => {
    render(
      <ConversationsView
        assistant={buildAssistant()}
        conversations={[conversation]}
        filters={{}}
        limit={20}
        offset={0}
        hasNext={false}
        hasActiveFilters={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "Conversations" })).toBeTruthy();
    expect(screen.getByLabelText("Conversation filters")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Conversation history results" })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Conversation pages" })).toBeTruthy();
    expect(screen.queryByText("No conversations have been recorded")).not.toBeInTheDocument();
  });

  it("shows the no-conversations empty state when there are no filters and no results", () => {
    render(
      <ConversationsView assistant={buildAssistant()} conversations={[]} filters={{}} limit={20} offset={0} hasNext={false} hasActiveFilters={false} />,
    );

    expect(screen.getByRole("heading", { name: "No conversations have been recorded" })).toBeTruthy();
  });

  it("shows the no-filter-results empty state when filters are active but return nothing", () => {
    render(
      <ConversationsView
        assistant={buildAssistant()}
        conversations={[]}
        filters={{ status: "archived" }}
        limit={20}
        offset={0}
        hasNext={false}
        hasActiveFilters
      />,
    );

    expect(screen.getByRole("heading", { name: "No conversations match these filters" })).toBeTruthy();
  });

  it("shows an archived-assistant notice when the assistant is archived", () => {
    render(
      <ConversationsView
        assistant={buildAssistant({ operational_status: "archived" })}
        conversations={[conversation]}
        filters={{}}
        limit={20}
        offset={0}
        hasNext={false}
        hasActiveFilters={false}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(/archived/i);
  });
});
