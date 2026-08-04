import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent, waitFor, within } from "../../test/test-utils";
import type { ConversationCitation, ConversationMessage } from "../../lib/api/types";
import { ConversationTranscript } from "./conversation-transcript";

const citation: ConversationCitation = {
  id: "citation-1",
  assistant_id: "assistant-1",
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
  assistant_id: "assistant-1",
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
  assistant_id: "assistant-1",
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

describe("ConversationTranscript", () => {
  it("renders messages in sequence with roles distinguishable by text", () => {
    render(<ConversationTranscript messages={[userMessage, assistantMessage]} assistantId="assistant-1" />);

    const bubbles = screen.getAllByRole("article");
    expect(within(bubbles[0]).getByText("User")).toBeTruthy();
    expect(within(bubbles[0]).getByText("How do we launch a workspace?")).toBeTruthy();
    expect(within(bubbles[1]).getByText("Assistant")).toBeTruthy();
    expect(within(bubbles[1]).getByText("Answered")).toBeTruthy();
  });

  it("renders citation chips and opens a drawer with full source detail on activation", async () => {
    const user = userEvent.setup();
    render(<ConversationTranscript messages={[assistantMessage]} assistantId="assistant-1" />);

    const chip = screen.getByRole("button", { name: "Open citation 1: Onboarding Guide" });
    expect(within(chip).getByText("Onboarding Guide")).toBeTruthy();
    expect(screen.queryByText("Invite the first workspace members before launch.")).not.toBeInTheDocument();

    await user.click(chip);

    expect(screen.getByRole("dialog", { name: /Onboarding Guide/ })).toBeTruthy();
    expect(screen.getByText("Invite the first workspace members before launch.")).toBeTruthy();
    expect(screen.getByText("0.876")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Close citation details" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("renders fallback and failed answer states clearly with a review-record link", () => {
    render(
      <ConversationTranscript
        assistantId="assistant-1"
        messages={[
          { ...assistantMessage, id: "fallback", answer_state: "fallback", content: "I do not have enough grounded context.", citations: [] },
          { ...assistantMessage, id: "failed", answer_state: "failed", content: "The provider failed before an answer was generated.", error_code: "provider_timeout", citations: [] },
        ]}
      />,
    );

    expect(screen.getByText("Fallback")).toBeTruthy();
    expect(screen.getByText("Failed")).toBeTruthy();
    expect(screen.getByText("provider_timeout")).toBeTruthy();
    const reviewLinks = screen.getAllByRole("link", { name: /Open review record/ });
    expect(reviewLinks).toHaveLength(2);
    expect(reviewLinks[0].getAttribute("href")).toBe("/review/unanswered/fallback?assistant=assistant-1");
  });

  it("does not show a review-record link for answered messages", () => {
    render(<ConversationTranscript messages={[assistantMessage]} assistantId="assistant-1" />);
    expect(screen.queryByRole("link", { name: /Open review record/ })).not.toBeInTheDocument();
  });

  it("copies the assistant answer to the clipboard", async () => {
    const user = userEvent.setup();
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      get: () => ({ writeText: writeTextMock }),
    });
    render(<ConversationTranscript messages={[assistantMessage]} assistantId="assistant-1" />);

    await user.click(screen.getByRole("button", { name: "Copy assistant answer" }));

    expect(writeTextMock).toHaveBeenCalledWith(assistantMessage.content);
    expect(await screen.findByText("Copied")).toBeTruthy();
  });

  it("renders allowed technical metadata and excludes restricted prompt content", () => {
    render(<ConversationTranscript messages={[assistantMessage]} assistantId="assistant-1" />);

    expect(screen.getByText("Technical details")).toBeTruthy();
    expect(screen.getByText("mock-default")).toBeTruthy();
    expect(screen.getByText("grounded_rag_answer")).toBeTruthy();
    expect(screen.queryByText("system prompt")).toBeNull();
    expect(screen.queryByText("secret")).toBeNull();
  });

  it("renders an empty state when there are no messages", () => {
    render(<ConversationTranscript messages={[]} assistantId="assistant-1" />);
    expect(screen.getByText("No messages recorded")).toBeTruthy();
  });

  it("handles missing citations safely", () => {
    render(<ConversationTranscript messages={[{ ...assistantMessage, citations: [] }]} assistantId="assistant-1" />);
    expect(screen.getByText(/No citations were returned/)).toBeTruthy();
  });
});
