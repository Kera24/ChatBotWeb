import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import type { ConversationDetail, ConversationMessage } from "../../lib/api/types";
import { ConversationQualityPanel, summarizeConversationQuality } from "./conversation-quality-panel";

function buildMessage(overrides: Partial<ConversationMessage>): ConversationMessage {
  return {
    id: "message-1",
    assistant_id: "assistant-1",
    role: "assistant",
    content: "Answer",
    sequence_number: 1,
    answer_state: "answered",
    model_key: "gpt-mock",
    provider_key: "mock",
    provider_model_name: "mock-grounded-v1",
    prompt_key: "grounded_rag_answer",
    prompt_version: 1,
    prompt_hash: "hash",
    execution_id: "execution-1",
    input_tokens: 50,
    output_tokens: 30,
    total_tokens: 80,
    estimated_cost: null,
    latency_ms: 120,
    finish_reason: "stop",
    error_code: null,
    created_at: "2026-07-12T02:00:00.000Z",
    citations: [],
    ...overrides,
  };
}

const baseConversation: ConversationDetail = {
  id: "conversation-1",
  assistant_id: "assistant-1",
  organisation_id: "org-1",
  workspace_id: "workspace-1",
  channel: "widget",
  status: "active",
  title: "Test conversation",
  started_at: "2026-07-12T01:00:00.000Z",
  last_message_at: "2026-07-12T02:00:00.000Z",
  ended_at: null,
  created_at: "2026-07-12T01:00:00.000Z",
  updated_at: "2026-07-12T02:00:00.000Z",
  metadata: null,
  messages: [],
};

describe("summarizeConversationQuality", () => {
  it("aggregates citation, token, and latency signals from assistant messages only", () => {
    const conversation: ConversationDetail = {
      ...baseConversation,
      messages: [
        { ...buildMessage({ id: "user-1", role: "user", answer_state: null, citations: [] }) },
        buildMessage({
          id: "assistant-1msg",
          citations: [
            { id: "c1", assistant_id: "assistant-1", citation_index: 1, chunk_id: "chunk-1", document_id: "doc-1", document_version_id: "v1", similarity_score: 0.9, source_title: "Doc A", source_type: "pdf", page_number: 1, section_title: null, quoted_text: "quote", created_at: "2026-07-12T02:00:00.000Z" },
          ],
        }),
        buildMessage({ id: "assistant-2msg", total_tokens: 60, latency_ms: 200, answer_state: "fallback" }),
      ],
    };

    const summary = summarizeConversationQuality(conversation);

    expect(summary.messageCount).toBe(3);
    expect(summary.assistantMessageCount).toBe(2);
    expect(summary.citationTotal).toBe(1);
    expect(summary.sourceCount).toBe(1);
    expect(summary.totalTokens).toBe(140);
    expect(summary.averageLatency).toBe(160);
    expect(summary.lastAnswerState).toBe("fallback");
    expect(summary.flaggedMessages).toHaveLength(1);
    expect(summary.flaggedMessages[0].id).toBe("assistant-2msg");
  });

  it("reports null signals when there are no assistant messages", () => {
    const summary = summarizeConversationQuality({ ...baseConversation, messages: [] });
    expect(summary.totalTokens).toBeNull();
    expect(summary.averageLatency).toBeNull();
    expect(summary.lastAnswerState).toBeNull();
    expect(summary.flaggedMessages).toHaveLength(0);
  });
});

describe("ConversationQualityPanel", () => {
  it("renders quality facts and links to the review queue, analytics, and knowledge base", () => {
    const summary = summarizeConversationQuality({ ...baseConversation, messages: [buildMessage({})] });
    render(<ConversationQualityPanel summary={summary} assistantId="assistant-1" />);

    const panel = screen.getByRole("complementary", { name: "Quality & metadata" });
    expect(within(panel).getByText("gpt-mock")).toBeTruthy();
    expect(within(panel).getByRole("link", { name: /Knowledge gap queue/ }).getAttribute("href")).toBe("/review/unanswered?assistant=assistant-1");
    expect(within(panel).getByRole("link", { name: /Assistant analytics/ }).getAttribute("href")).toBe("/analytics?assistant=assistant-1");
    expect(within(panel).getByRole("link", { name: /Knowledge base/ }).getAttribute("href")).toBe("/knowledge?assistant=assistant-1");
  });

  it("lists flagged messages with links to their review record", () => {
    const summary = summarizeConversationQuality({
      ...baseConversation,
      messages: [buildMessage({ id: "flagged-1", answer_state: "fallback" })],
    });
    render(<ConversationQualityPanel summary={summary} assistantId="assistant-1" />);

    const link = screen.getByRole("link", { name: /Open review record/ });
    expect(link.getAttribute("href")).toBe("/review/unanswered/flagged-1?assistant=assistant-1");
  });

  it("shows a reassuring note when there are no knowledge gap items", () => {
    const summary = summarizeConversationQuality({ ...baseConversation, messages: [buildMessage({ answer_state: "answered" })] });
    render(<ConversationQualityPanel summary={summary} assistantId="assistant-1" />);

    expect(screen.getByText(/No fallback, low-confidence, or failed responses/)).toBeTruthy();
  });
});
