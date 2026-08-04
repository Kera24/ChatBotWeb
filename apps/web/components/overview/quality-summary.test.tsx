import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { OverviewData } from "../../lib/api/overview";
import type { ReviewItem } from "../../lib/api/types";
import { QualitySummary } from "./quality-summary";

function buildReviewItem(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    conversation_id: "conversation-1",
    assistant_id: "assistant-1",
    assistant_message_id: "message-1",
    user_question: "What is the deadline?",
    assistant_answer: "I do not have enough context.",
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
    created_at: "2026-01-01T00:00:00.000Z",
    estimated_cost: null,
    latency_ms: 120,
    review_status: "open",
    reviewer_note: null,
    reviewed_at: null,
    reviewed_by: null,
    ...overrides,
  };
}

describe("QualitySummary", () => {
  it("labels recent conversations as a bounded window, not an all-time total", () => {
    const data: OverviewData = { documents: [], conversations: [{ id: "c1", assistant_id: "assistant-1", organisation_id: "o", workspace_id: "w", channel: "widget", status: "active", title: null, started_at: "2026-01-01T00:00:00.000Z", last_message_at: null, ended_at: null, message_count: 1, last_message_preview: null, metadata: null }], widgets: [], reviewItems: [], reviewTotal: 0 };
    render(<QualitySummary data={data} recentWindowLimit={50} />);
    expect(screen.getByText(/bounded window of up to 50 per assistant/)).toBeTruthy();
  });

  it("breaks down open review items by answer state without claiming an overall fallback rate", () => {
    const data: OverviewData = { documents: [], conversations: [], widgets: [], reviewItems: [buildReviewItem(), buildReviewItem({ assistant_message_id: "m2", answer_state: "low_confidence" })], reviewTotal: 2 };
    render(<QualitySummary data={data} recentWindowLimit={50} />);

    expect(screen.getByText("Open review items by answer state")).toBeTruthy();
    expect(screen.queryByText(/fallback rate/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/hallucination/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/citation accuracy/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/customer satisfaction/i)).not.toBeInTheDocument();
  });

  it("shows a no-sample message when there are no open review items", () => {
    const data: OverviewData = { documents: [], conversations: [], widgets: [], reviewItems: [], reviewTotal: 0 };
    render(<QualitySummary data={data} recentWindowLimit={50} />);
    expect(screen.getByText(/No open review items in the current sample/)).toBeTruthy();
  });

  it("clearly scopes latency to the sampled review items", () => {
    const data: OverviewData = { documents: [], conversations: [], widgets: [], reviewItems: [buildReviewItem()], reviewTotal: 1 };
    render(<QualitySummary data={data} recentWindowLimit={50} />);
    expect(screen.getByText(/sampled above, not all conversations/)).toBeTruthy();
  });
});
