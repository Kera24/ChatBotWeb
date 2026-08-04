import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { ConversationSummary } from "../../lib/api/types";
import { ConversationInbox, formatDate, formatEnum } from "./conversation-list";

const conversation: ConversationSummary = {
  id: "conversation-12345678",
  assistant_id: "assistant-1",
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

describe("ConversationInbox", () => {
  it("renders conversations as accessible cards with status, preview, facts, and links", () => {
    render(<ConversationInbox conversations={[conversation]} assistantId="assistant-1" assistantLabel="Admissions Assistant" />);

    expect(screen.getByRole("list", { name: "Conversation history results" })).toBeTruthy();
    const link = screen.getByRole("link", { name: /Pricing question/ });
    expect(link.getAttribute("href")).toBe("/conversations/conversation-12345678?assistant=assistant-1");
    expect(screen.getByText("Pricing question")).toBeTruthy();
    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByText("The answer should reference the onboarding guide.")).toBeTruthy();
    expect(screen.getByText("dashboard test")).toBeTruthy();
    expect(screen.getByText("Admissions Assistant")).toBeTruthy();
  });

  it("renders a sensible fallback title and empty preview", () => {
    render(<ConversationInbox conversations={[{ ...conversation, title: null, last_message_preview: null }]} assistantId="assistant-1" />);

    expect(screen.getByText("Conversation conversa")).toBeTruthy();
    expect(screen.getByText("No messages have been recorded yet.")).toBeTruthy();
  });

  it("falls back to the provided assistantId when a conversation has no assistant_id", () => {
    render(<ConversationInbox conversations={[{ ...conversation, assistant_id: null }]} assistantId="assistant-fallback" />);

    const link = screen.getByRole("link", { name: /Pricing question/ });
    expect(link.getAttribute("href")).toBe("/conversations/conversation-12345678?assistant=assistant-fallback");
  });
});

describe("conversation-list formatters", () => {
  it("formats enums by replacing underscores", () => {
    expect(formatEnum("dashboard_test")).toBe("dashboard test");
    expect(formatEnum(null)).toBe("unknown");
  });

  it("formats dates", () => {
    expect(formatDate("2026-07-12T01:00:00.000Z")).toContain("2026");
  });
});
