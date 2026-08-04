import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatbotClient } from "./chatbot-client";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-abc",
  workspaceId: "workspace-def",
  userEmail: "admin@example.test",
  role: "client_admin",
};

const answerPayload = {
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
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

function mockAnswerResponse(data = answerPayload) {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data, meta: {} }), { status: 200 })));
}

describe("ChatbotClient", () => {
  it("sends an assistant-scoped RAG question and renders answer citations", async () => {
    mockAnswerResponse();
    render(<ChatbotClient session={session} assistantId="assistant-1" />);

    expect(screen.getByLabelText("Selected assistant context")).toHaveTextContent("assistant-1");
    expect(screen.getByRole("link", { name: /^Knowledge$/ })).toHaveAttribute("href", "/knowledge?assistant=assistant-1");

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "When do applications close?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("When do applications close?")).toBeTruthy();
    expect(await screen.findByText("Applications close in December [1].")).toBeTruthy();
    expect(screen.getByRole("button", { name: /open citation 1: admissions handbook/i })).toBeTruthy();
    expect(screen.getByText("Conversation conversa")).toBeTruthy();

    const request = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({ query: "When do applications close?", assistant_id: "assistant-1" });
  });

  it("reuses the conversation id for the next assistant-scoped message", async () => {
    mockAnswerResponse();
    render(<ChatbotClient session={session} assistantId="assistant-1" />);

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "First question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("Applications close in December [1].");

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Second question" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    const second = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[1][1] as RequestInit;
    expect(JSON.parse(String(second.body))).toEqual({ query: "Second question", assistant_id: "assistant-1", conversation_id: "conversation-123" });
  });

  it("shows fallback handling when the endpoint returns a fallback answer", async () => {
    mockAnswerResponse({ ...answerPayload, answer: "The knowledge base does not contain enough information.", answer_state: "fallback", citations: [], retrieved_chunk_count: 0, latency_ms: 12, fallback_used: true });
    render(<ChatbotClient session={session} assistantId="assistant-1" />);

    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Unknown topic" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("The knowledge base does not contain enough information.")).toBeTruthy();
    expect(screen.getByText("The assistant used the safe fallback path because indexed context was insufficient or unavailable.")).toBeTruthy();
    expect(screen.getByLabelText("Answer state: fallback")).toBeTruthy();
  });

  it("opens citation source details and copies an assistant answer", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    mockAnswerResponse();
    render(<ChatbotClient session={session} assistantId="assistant-1" />);

    await user.type(screen.getByLabelText("Message"), "When do applications close?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("Applications close in December [1].");

    await user.click(screen.getByRole("button", { name: /open citation 1: admissions handbook/i }));
    const drawer = screen.getByRole("dialog", { name: /admissions handbook/i });
    expect(within(drawer).getByText("Applications close in December.")).toBeTruthy();
    expect(within(drawer).getByText("0.910")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Copy assistant answer" }));
    expect(writeText).toHaveBeenCalledWith("Applications close in December [1].");
    expect(await screen.findByText("Copied")).toBeTruthy();
  });

  it("submits with Enter and preserves Shift Enter for new lines", async () => {
    mockAnswerResponse();
    render(<ChatbotClient session={session} assistantId="assistant-1" />);
    const composer = screen.getByLabelText("Message");

    fireEvent.change(composer, { target: { value: "Line one" } });
    fireEvent.keyDown(composer, { key: "Enter", shiftKey: true });
    expect(fetch).not.toHaveBeenCalled();

    fireEvent.keyDown(composer, { key: "Enter" });
    expect(await screen.findByText("Line one")).toBeTruthy();
  });

  it("renders missing assistant and API error states", async () => {
    const missing = render(<ChatbotClient session={session} assistantId="" missingAssistant />);
    expect(screen.getByRole("alert")).toHaveTextContent("Select an assistant");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    missing.unmount();

    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    const user = userEvent.setup();
    render(<ChatbotClient session={session} assistantId="assistant-1" />);
    await user.type(screen.getByLabelText("Message"), "Fail");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(await screen.findByText(/API could not be reached/i)).toBeTruthy();
  });
});
