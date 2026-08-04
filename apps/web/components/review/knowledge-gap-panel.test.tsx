import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { ReviewItem } from "../../lib/api/types";
import { deriveKnowledgeGuidance, KnowledgeGapPanel } from "./knowledge-gap-panel";

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
  created_at: "2026-07-12T00:00:00.000Z",
  estimated_cost: null,
  latency_ms: null,
  review_status: "open",
  reviewer_note: null,
  reviewed_at: null,
  reviewed_by: null,
};

describe("deriveKnowledgeGuidance", () => {
  it("flags missing citations and a likely knowledge gap when there are zero sources and a fallback answer", () => {
    const guidance = deriveKnowledgeGuidance(baseItem);
    const ids = guidance.map((entry) => entry.id);
    expect(ids).toContain("missing-citations");
    expect(ids).toContain("fallback-answer");
    expect(ids).toContain("likely-knowledge-gap");
  });

  it("suggests a document update when citations exist but the answer still failed", () => {
    const guidance = deriveKnowledgeGuidance({ ...baseItem, citation_count: 2, answer_state: "failed", error_code: "provider_timeout" });
    const ids = guidance.map((entry) => entry.id);
    expect(ids).toContain("has-citations");
    expect(ids).toContain("failed-answer");
    expect(ids).toContain("needs-document-update");
    expect(ids).not.toContain("missing-citations");
    expect(ids).not.toContain("likely-knowledge-gap");
  });

  it("notes when an item has already been confirmed as a knowledge gap", () => {
    const guidance = deriveKnowledgeGuidance({ ...baseItem, review_status: "knowledge_gap" });
    expect(guidance.map((entry) => entry.id)).toContain("confirmed-gap");
  });

  it("never invents a numeric AI score", () => {
    const guidance = deriveKnowledgeGuidance(baseItem);
    for (const entry of guidance) {
      expect(entry.detail).not.toMatch(/\d+%|score of \d/i);
    }
  });
});

describe("KnowledgeGapPanel", () => {
  it("renders guidance cards with a disclosure that this is not an AI score", () => {
    render(<KnowledgeGapPanel item={baseItem} />);
    expect(screen.getByRole("heading", { name: "Guidance from existing signals" })).toBeTruthy();
    expect(screen.getByText("Missing citations")).toBeTruthy();
    expect(screen.getByText(/not an AI-generated quality score/i)).toBeTruthy();
  });
});
