import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { ConversationSummary } from "../../lib/api/types";
import { ConversationList } from "./conversation-list";

const conversation: ConversationSummary = {
  id: "conversation-12345678",
  organisation_id: "org-1",
  workspace_id: "workspace-1",
  channel: "dashboard_test",
  status: "active",
  title: "Pricing question",
  started_at: "2026-07-12T01:00:00.000Z",
  last_message_at: "2026-07-12T01:03:00.000Z",
  ended_at: null,
  message_count: 2,
  last_message_preview: "The answer should reference the onboarding guide.",
  metadata: {},
};

describe("ConversationList", () => {
  it("renders conversations with status, preview, facts, and links", () => {
    render(<ConversationList conversations={[conversation]} />);

    const link = screen.getByRole("link", { name: "Pricing question" });
    expect(link.getAttribute("href")).toBe("/conversations/conversation-12345678");
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByText("The answer should reference the onboarding guide.")).toBeTruthy();
    expect(screen.getByText("dashboard test")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
  });

  it("renders a sensible fallback title and empty preview", () => {
    render(<ConversationList conversations={[{ ...conversation, title: null, last_message_preview: null }]} />);

    expect(screen.getByRole("link", { name: "Conversation conversa" })).toBeTruthy();
    expect(screen.getByText("No messages have been recorded yet.")).toBeTruthy();
  });
});
