import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import type { ReviewItem } from "../../lib/api/types";
import { ReviewMetrics, summarizeSampleSignals } from "./review-metrics";

function hoursAgo(hours: number) {
  return new Date(Date.now() - hours * 60 * 60_000).toISOString();
}

const baseItem: ReviewItem = {
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
  created_at: hoursAgo(5),
  estimated_cost: null,
  latency_ms: null,
  review_status: "open",
  reviewer_note: null,
  reviewed_at: null,
  reviewed_by: null,
};

describe("summarizeSampleSignals", () => {
  it("counts items reviewed today and computes an average review age", () => {
    const items: ReviewItem[] = [
      { ...baseItem, assistant_message_id: "a", reviewed_at: new Date().toISOString(), created_at: hoursAgo(2) },
      { ...baseItem, assistant_message_id: "b", reviewed_at: new Date().toISOString(), created_at: hoursAgo(4) },
      { ...baseItem, assistant_message_id: "c", reviewed_at: null },
    ];

    const signals = summarizeSampleSignals(items);
    expect(signals.reviewedToday).toBe(2);
    expect(signals.sampleSize).toBe(3);
    expect(signals.averageReviewAgeLabel).toMatch(/hr|min/);
  });

  it("reports no sample when nothing has been reviewed", () => {
    const signals = summarizeSampleSignals([{ ...baseItem, reviewed_at: null }]);
    expect(signals.reviewedToday).toBe(0);
    expect(signals.averageReviewAgeLabel).toBe("No sample");
  });
});

describe("ReviewMetrics", () => {
  it("renders all-time totals and page-sample caveats", () => {
    render(
      <ReviewMetrics
        data={{ pending: 12, resolved: 30, needsKnowledge: 4, fallbacks: 18, lowConfidence: 9, failed: 3 }}
        sample={{ reviewedToday: 2, averageReviewAgeLabel: "3 hr", sampleSize: 20 }}
      />,
    );

    const grid = screen.getByLabelText("Review queue summary metrics");
    expect(within(grid).getByText("Pending")).toBeTruthy();
    expect(within(grid).getByText("12")).toBeTruthy();
    expect(within(grid).getByText("Resolved")).toBeTruthy();
    expect(within(grid).getByText("30")).toBeTruthy();
    expect(within(grid).getByText("Needs knowledge")).toBeTruthy();
    expect(within(grid).getByText("Reviewed today")).toBeTruthy();
    expect(within(grid).getByText("Average review age")).toBeTruthy();
    expect(within(grid).getByText("3 hr")).toBeTruthy();
    expect(within(grid).getByText(/From the 20 items on this page/)).toBeTruthy();
  });
});
