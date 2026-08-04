import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import type { ReviewItem } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { ReviewQualityPanel } from "./review-quality-panel";

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
  model_key: "mock-default",
  provider_key: "mock",
  prompt_key: "grounded_rag_answer",
  prompt_version: 1,
  citation_count: 2,
  citations: [
    { id: "c1", assistant_id: "assistant-1", citation_index: 1, chunk_id: "chunk-1", document_id: "doc-1", document_version_id: "v1", similarity_score: 0.9, source_title: "Doc A", source_type: "pdf", page_number: 1, section_title: null, quoted_text: "quote", created_at: "2026-07-12T00:00:00.000Z" },
    { id: "c2", assistant_id: "assistant-1", citation_index: 2, chunk_id: "chunk-2", document_id: "doc-1", document_version_id: "v1", similarity_score: 0.8, source_title: "Doc A", source_type: "pdf", page_number: 2, section_title: null, quoted_text: "quote 2", created_at: "2026-07-12T00:00:00.000Z" },
  ],
  created_at: "2026-07-12T00:00:00.000Z",
  estimated_cost: null,
  latency_ms: 120,
  review_status: "open",
  reviewer_note: null,
  reviewed_at: null,
  reviewed_by: null,
};

describe("ReviewQualityPanel", () => {
  it("renders review status, answer state, citation and source counts, latency, provider, model, assistant, and workspace", () => {
    render(<ReviewQualityPanel item={item} assistant={buildAssistant()} workspaceId="workspace-1" />);

    const panel = screen.getByRole("complementary", { name: "Quality & metadata" });
    expect(within(panel).getByText("open")).toBeTruthy();
    expect(within(panel).getByText("fallback")).toBeTruthy();
    expect(within(panel).getByText("2")).toBeTruthy();
    expect(within(panel).getByText("1")).toBeTruthy();
    expect(within(panel).getByText("120 ms")).toBeTruthy();
    expect(within(panel).getByText("mock")).toBeTruthy();
    expect(within(panel).getByText("mock-default")).toBeTruthy();
    expect(within(panel).getByText("Admissions Assistant")).toBeTruthy();
    expect(within(panel).getByText("workspace-1")).toBeTruthy();
  });

  it("shows a no-sample placeholder for missing latency and provider data", () => {
    render(<ReviewQualityPanel item={{ ...item, latency_ms: null, provider_key: null, model_key: null }} assistant={buildAssistant()} workspaceId="workspace-1" />);
    expect(screen.getAllByText("No sample").length).toBeGreaterThanOrEqual(3);
  });
});
