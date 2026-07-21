import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import type { ConversationCitation, ConversationMessage } from "../../lib/api/types";
import { CitationList } from "./citation-list";
import { MessageThread } from "./message-thread";

const citation: ConversationCitation = {
  id: "citation-1",
  citation_index: 1,
  chunk_id: "chunk-1",
  document_id: "document-1",
  document_version_id: "version-1",
  similarity_score: "0.8765",
  source_title: "Onboarding Guide",
  source_type: "pdf",
  page_number: 4,
  section_title: "Activation",
  quoted_text: "Invite the first workspace members before launch.",
  created_at: "2026-07-12T02:00:00.000Z",
};

const userMessage: ConversationMessage = {
  id: "message-user",
  role: "user",
  content: "How do we launch a workspace?",
  sequence_number: 1,
  answer_state: null,
  model_key: null,
  provider_key: null,
  provider_model_name: null,
  prompt_key: null,
  prompt_version: null,
  prompt_hash: null,
  execution_id: null,
  input_tokens: null,
  output_tokens: null,
  total_tokens: null,
  estimated_cost: null,
  latency_ms: null,
  finish_reason: null,
  error_code: null,
  created_at: "2026-07-12T02:00:00.000Z",
  citations: [],
};

const assistantMessage: ConversationMessage = {
  id: "message-assistant",
  role: "assistant",
  content: "Invite the first workspace members and confirm the source-grounded configuration.",
  sequence_number: 2,
  answer_state: "answered",
  model_key: "mock-default",
  provider_key: "mock",
  provider_model_name: "mock-grounded-v1",
  prompt_key: "grounded_rag_answer",
  prompt_version: 3,
  prompt_hash: "prompt-hash-123",
  execution_id: "execution-123",
  input_tokens: 100,
  output_tokens: 40,
  total_tokens: 140,
  estimated_cost: "0.0014",
  latency_ms: 42,
  finish_reason: "stop",
  error_code: null,
  created_at: "2026-07-12T02:00:01.000Z",
  citations: [citation],
};

describe("MessageThread", () => {
  it("renders messages in sequence with roles distinguishable by text", () => {
    render(<MessageThread messages={[userMessage, assistantMessage]} />);

    const bubbles = screen.getAllByRole("article");
    expect(within(bubbles[0]).getByText("User")).toBeTruthy();
    expect(within(bubbles[0]).getByText("How do we launch a workspace?")).toBeTruthy();
    expect(within(bubbles[1]).getByText("Assistant")).toBeTruthy();
    expect(within(bubbles[1]).getByText("Answered")).toBeTruthy();
  });

  it("renders citations under the assistant message that owns them", () => {
    render(<MessageThread messages={[userMessage, assistantMessage]} />);

    const assistantBubble = screen.getAllByRole("article")[1];
    expect(within(assistantBubble).getByText("[1] Onboarding Guide")).toBeTruthy();
    expect(within(assistantBubble).getByText("Invite the first workspace members before launch.")).toBeTruthy();
    expect(within(assistantBubble).getByText("0.876")).toBeTruthy();
  });

  it("renders fallback and failed answer states clearly", () => {
    render(
      <MessageThread
        messages={[
          { ...assistantMessage, id: "fallback", answer_state: "fallback", content: "I do not have enough grounded context.", citations: [] },
          { ...assistantMessage, id: "failed", answer_state: "failed", content: "The provider failed before an answer was generated.", error_code: "provider_timeout", citations: [] },
        ]}
      />,
    );

    expect(screen.getByText("Fallback")).toBeTruthy();
    expect(screen.getByText("Failed")).toBeTruthy();
    expect(screen.getByText("provider_timeout")).toBeTruthy();
  });

  it("renders allowed technical metadata and excludes restricted prompt content", () => {
    render(<MessageThread messages={[assistantMessage]} />);

    expect(screen.getByText("Technical details")).toBeTruthy();
    expect(screen.getByText("mock-default")).toBeTruthy();
    expect(screen.getByText("grounded_rag_answer")).toBeTruthy();
    expect(screen.getByText("0.0014")).toBeTruthy();
    expect(screen.queryByText("system prompt")).toBeNull();
    expect(screen.queryByText("rendered prompt")).toBeNull();
    expect(screen.queryByText("secret")).toBeNull();
  });

  it("handles missing citations safely", () => {
    render(<MessageThread messages={[{ ...assistantMessage, citations: [] }]} />);

    expect(screen.queryByLabelText("Assistant citations")).toBeNull();
    expect(screen.getByText("Assistant")).toBeTruthy();
  });
});

describe("CitationList", () => {
  it("renders citation metadata without requiring hover", () => {
    render(<CitationList citations={[citation]} />);

    expect(screen.getByLabelText("Assistant citations")).toBeTruthy();
    expect(screen.getByText("[1] Onboarding Guide")).toBeTruthy();
    expect(screen.getByText("pdf")).toBeTruthy();
    expect(screen.getByText("Activation")).toBeTruthy();
  });

  it("renders nothing when no citations are present", () => {
    const { container } = render(<CitationList citations={[]} />);

    expect(container.textContent).toBe("");
  });
});
