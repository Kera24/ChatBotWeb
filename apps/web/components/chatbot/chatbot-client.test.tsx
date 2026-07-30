import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatbotClient } from "./chatbot-client";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-abc",
  workspaceId: "workspace-def",
  userEmail: "admin@example.test",
  role: "client_admin",
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

function mockAnswerResponse() {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({
      success: true,
      data: {
        conversation_id: "conversation-123",
        user_message_id: "user-1",
        assistant_message_id: "assistant-1",
        answer: "Applications close in December [1].",
        answer_state: "answered",
        citations: [{
          citation_index: 1,
          chunk_id: "chunk-1",
          document_id: "document-1",
          document_version_id: "version-1",
          source_title: "Admissions Handbook",
          source_type: "txt",
          page_number: 4,
          section_title: "Admissions",
          similarity_score: 0.91,
          quoted_text: "Applications close in December.",
        }],
        retrieved_chunk_count: 1,
        provider_key: "mock",
        model_key: "mock-grounded-answer",
        provider_model_name: "mock",
        prompt_key: "grounded_rag_answer",
        prompt_version: "1",
        prompt_hash: "hash",
        execution_id: "execution-1",
        token_usage: { total_tokens: 12 },
        estimated_cost: "0",
        latency_ms: 34,
        finish_reason: "stop",
        fallback_used: false,
      },
      meta: {},
    }), { status: 200 })),
  );
}

describe("ChatbotClient", () => {
  it("sends a workspace RAG question and renders answer citations", async () => {
    mockAnswerResponse();
    render(<ChatbotClient session={session} />);

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "When do applications close?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("When do applications close?")).toBeTruthy();
    expect(await screen.findByText("Applications close in December [1].")).toBeTruthy();
    expect(screen.getByText("[1] Admissions Handbook")).toBeTruthy();
    expect(screen.getByText("Conversation conversa")).toBeTruthy();
  });

  it("reuses the conversation id for the next message", async () => {
    mockAnswerResponse();
    render(<ChatbotClient session={session} />);

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "First question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("Applications close in December [1].");

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Second question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    const second = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[1][1] as RequestInit;
    expect(JSON.parse(String(second.body))).toEqual({
      query: "Second question",
      conversation_id: "conversation-123",
    });
  });

  it("shows fallback handling when the endpoint returns a fallback answer", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({
        success: true,
        data: {
          conversation_id: "conversation-123",
          user_message_id: "user-1",
          assistant_message_id: "assistant-1",
          answer: "The knowledge base does not contain enough information.",
          answer_state: "fallback",
          citations: [],
          retrieved_chunk_count: 0,
          provider_key: "mock",
          model_key: "mock-grounded-answer",
          provider_model_name: "mock",
          prompt_key: "grounded_rag_answer",
          prompt_version: "1",
          prompt_hash: "hash",
          execution_id: "execution-1",
          token_usage: { total_tokens: 8 },
          estimated_cost: "0",
          latency_ms: 12,
          finish_reason: "stop",
          fallback_used: true,
        },
        meta: {},
      }), { status: 200 })),
    );
    render(<ChatbotClient session={session} />);

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Unknown topic" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("The knowledge base does not contain enough information.")).toBeTruthy();
    expect(screen.getByText("The assistant used the safe fallback path because indexed context was insufficient or unavailable.")).toBeTruthy();
  });
});
