import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { ReviewItem } from "../../lib/api/types";
import { deriveReviewPriority, ReviewList } from "./review-list";

function minutesAgo(minutes: number) {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

const item: ReviewItem = {
  conversation_id: "conversation-1",
  assistant_id: "assistant-1",
  assistant_message_id: "assistant-message-1",
  user_question: "What is the refund policy?",
  assistant_answer: "I do not have enough grounded context to answer.",
  answer_state: "fallback",
  error_code: null,
  channel: "dashboard_test",
  conversation_status: "active",
  model_key: "mock-default",
  provider_key: "mock",
  prompt_key: "grounded_rag_answer",
  prompt_version: 1,
  citation_count: 0,
  citations: [],
  created_at: minutesAgo(10),
  estimated_cost: "0.0001",
  latency_ms: 33,
  review_status: "open",
  reviewer_note: null,
  reviewed_at: null,
  reviewed_by: null,
};

describe("ReviewList", () => {
  it("renders review cards as an accessible list with distinct states and review status", () => {
    render(
      <ReviewList
        items={[
          item,
          { ...item, assistant_message_id: "assistant-message-2", answer_state: "failed", error_code: "provider_timeout", review_status: "knowledge_gap" },
          { ...item, assistant_message_id: "assistant-message-3", answer_state: "low_confidence", review_status: "dismissed" },
        ]}
        assistantId="assistant-1"
        assistantLabel="Admissions Assistant"
      />,
    );

    expect(screen.getByRole("list", { name: "Knowledge gap review results" })).toBeTruthy();
    expect(screen.getAllByText("What is the refund policy?").length).toBe(3);
    expect(screen.getByText("Fallback")).toBeTruthy();
    expect(screen.getByText("Failed")).toBeTruthy();
    expect(screen.getByText("Low confidence")).toBeTruthy();
    expect(screen.getByText("Knowledge gap")).toBeTruthy();
    expect(screen.getByText("Dismissed")).toBeTruthy();
    expect(screen.getAllByText("Admissions Assistant").length).toBe(3);
  });

  it("links each card to its review detail page preserving assistant context", () => {
    render(<ReviewList items={[item]} assistantId="assistant-1" />);
    const link = screen.getByRole("link", { name: /What is the refund policy/ });
    expect(link.getAttribute("href")).toBe("/review/unanswered/assistant-message-1?assistant=assistant-1");
  });

  it("shows a no-sources knowledge indicator when there are zero citations", () => {
    render(<ReviewList items={[item]} assistantId="assistant-1" />);
    expect(screen.getByText("No sources retrieved")).toBeTruthy();
  });

  it("shows a source count indicator when citations exist", () => {
    render(<ReviewList items={[{ ...item, citation_count: 2 }]} assistantId="assistant-1" />);
    expect(screen.getByText("2 sources")).toBeTruthy();
  });
});

describe("deriveReviewPriority", () => {
  it("marks failed, still-open items as high priority", () => {
    const priority = deriveReviewPriority({ ...item, answer_state: "failed", review_status: "open" });
    expect(priority.level).toBe("high");
  });

  it("marks long-open fallback items as high priority", () => {
    const priority = deriveReviewPriority({ ...item, answer_state: "fallback", review_status: "open", created_at: new Date(Date.now() - 5 * 86_400_000).toISOString() });
    expect(priority.level).toBe("high");
  });

  it("marks recently-open fallback items as medium priority", () => {
    const priority = deriveReviewPriority({ ...item, answer_state: "fallback", review_status: "open", created_at: minutesAgo(10) });
    expect(priority.level).toBe("medium");
  });

  it("marks already-resolved items as low priority regardless of answer state", () => {
    const priority = deriveReviewPriority({ ...item, answer_state: "failed", review_status: "reviewed" });
    expect(priority.level).toBe("low");
  });
});
