import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import type { ConversationDetail } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { ConversationArchivedNotice, ConversationDetailHeader, ConversationsListHeader } from "./conversation-header";

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

describe("ConversationsListHeader", () => {
  it("shows assistant identity, status, count, and preserves assistant context in quick links", () => {
    render(<ConversationsListHeader assistant={buildAssistant()} visibleCount={4} periodLabel="Most recent conversations, up to 20 per page" />);

    expect(screen.getByRole("heading", { name: "Conversations" })).toBeTruthy();
    expect(screen.getByText(/Admissions Assistant/)).toBeTruthy();
    expect(screen.getByText("4 conversations on this page")).toBeTruthy();
    expect(screen.getByText("Most recent conversations, up to 20 per page")).toBeTruthy();

    const nav = screen.getByRole("navigation", { name: "Assistant quick links" });
    expect(within(nav).getByRole("link", { name: /Playground/ }).getAttribute("href")).toBe("/chatbot?assistant=assistant-1");
    expect(within(nav).getByRole("link", { name: /Analytics/ }).getAttribute("href")).toBe("/analytics?assistant=assistant-1");
    expect(within(nav).getByRole("link", { name: /Knowledge Gaps/ }).getAttribute("href")).toBe("/review/unanswered?assistant=assistant-1");
  });
});

describe("ConversationDetailHeader", () => {
  const conversation: ConversationDetail = {
    id: "conversation-1",
    assistant_id: "assistant-1",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    channel: "widget",
    status: "completed",
    title: "Pricing question",
    started_at: "2026-07-12T01:00:00.000Z",
    last_message_at: "2026-07-12T01:05:00.000Z",
    ended_at: null,
    created_at: "2026-07-12T01:00:00.000Z",
    updated_at: "2026-07-12T01:05:00.000Z",
    metadata: null,
    messages: [],
  };

  it("shows conversation identity, status, timestamps, and assistant context", () => {
    render(<ConversationDetailHeader conversation={conversation} assistant={buildAssistant()} />);

    expect(screen.getByRole("heading", { name: "Pricing question" })).toBeTruthy();
    expect(screen.getByText("Completed")).toBeTruthy();
    expect(screen.getByText("Assistant Admissions Assistant")).toBeTruthy();
    expect(screen.getByText("widget")).toBeTruthy();
  });

  it("falls back to a short id when no title is present", () => {
    render(<ConversationDetailHeader conversation={{ ...conversation, title: null }} assistant={buildAssistant()} />);
    expect(screen.getByRole("heading", { name: "Conversation conversa" })).toBeTruthy();
  });
});

describe("ConversationArchivedNotice", () => {
  it("renders a non-blocking status notice", () => {
    render(<ConversationArchivedNotice />);
    expect(screen.getByRole("status")).toHaveTextContent(/archived/i);
  });
});
