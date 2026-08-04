import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import type { ReviewItem } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { ReviewArchivedNotice, ReviewDetailHeader, ReviewQueueHeader } from "./review-header";

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

describe("ReviewQueueHeader", () => {
  it("shows assistant identity, pending/resolved counts, and quick links preserving assistant context", () => {
    render(<ReviewQueueHeader assistant={buildAssistant()} pending={5} resolved={12} totalInFilter={3} periodLabel="Most recent flagged answers" />);

    expect(screen.getByRole("heading", { name: "Review Queue" })).toBeTruthy();
    expect(screen.getByText(/Admissions Assistant/)).toBeTruthy();
    expect(screen.getByText("5 pending")).toBeTruthy();
    expect(screen.getByText("12 resolved")).toBeTruthy();
    expect(screen.getByText("3 in current filter")).toBeTruthy();

    const nav = screen.getByRole("navigation", { name: "Assistant quick links" });
    expect(within(nav).getByRole("link", { name: /Knowledge/ }).getAttribute("href")).toBe("/knowledge?assistant=assistant-1");
    expect(within(nav).getByRole("link", { name: /Chat Playground/ }).getAttribute("href")).toBe("/chatbot?assistant=assistant-1");
    expect(within(nav).getByRole("link", { name: /Analytics/ }).getAttribute("href")).toBe("/analytics?assistant=assistant-1");
    expect(within(nav).getByRole("link", { name: /Conversations/ }).getAttribute("href")).toBe("/conversations?assistant=assistant-1");
  });
});

describe("ReviewDetailHeader", () => {
  const item: ReviewItem = {
    conversation_id: "conversation-1",
    assistant_id: "assistant-1",
    assistant_message_id: "assistant-message-1",
    user_question: "What is the refund policy?",
    assistant_answer: "Answer",
    answer_state: "fallback",
    error_code: null,
    channel: "widget",
    conversation_status: "active",
    model_key: null,
    provider_key: null,
    prompt_key: null,
    prompt_version: null,
    citation_count: 0,
    citations: [],
    created_at: "2026-07-12T00:00:00.000Z",
    estimated_cost: null,
    latency_ms: null,
    review_status: "open",
    reviewer_note: null,
    reviewed_at: null,
    reviewed_by: null,
  };

  it("shows the question, answer state, review state, and assistant context", () => {
    render(<ReviewDetailHeader item={item} assistant={buildAssistant()} />);

    expect(screen.getByRole("heading", { name: "What is the refund policy?" })).toBeTruthy();
    expect(screen.getByText("Fallback")).toBeTruthy();
    expect(screen.getByText("Open")).toBeTruthy();
    expect(screen.getByText("Assistant Admissions Assistant")).toBeTruthy();
  });
});

describe("ReviewArchivedNotice", () => {
  it("renders a non-blocking status notice", () => {
    render(<ReviewArchivedNotice />);
    expect(screen.getByRole("status")).toHaveTextContent(/archived/i);
  });
});
