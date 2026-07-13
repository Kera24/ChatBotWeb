import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent, within } from "../../test/test-utils";
import type { ConversationMessage, ReviewItem, ReviewItemDetail } from "../../lib/api/types";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { ReviewDecisionForm } from "./review-decision-form";
import { ReviewDetail } from "./review-detail";
import { ReviewFilters } from "./review-filters";
import { ReviewList } from "./review-list";
import { ReviewPaginationControls } from "./review-pagination-controls";
import { ReviewStatusBadge } from "./review-status-badge";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

const item: ReviewItem = {
  conversation_id: "conversation-1",
  assistant_message_id: "assistant-1",
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
  citation_count: 1,
  citations: [
    {
      id: "citation-1",
      citation_index: 1,
      chunk_id: "chunk-1",
      document_id: "document-1",
      document_version_id: "version-1",
      similarity_score: "0.9",
      source_title: "Refund Guide",
      source_type: "txt",
      page_number: null,
      section_title: "Policy",
      quoted_text: "Refunds are processed within five days.",
      created_at: "2026-07-12T00:00:00.000Z",
    },
  ],
  created_at: "2026-07-12T00:00:00.000Z",
  estimated_cost: "0.00010000",
  latency_ms: 33,
  review_status: "open",
  reviewer_note: null,
  reviewed_at: null,
  reviewed_by: null,
};

const userMessage: ConversationMessage = {
  id: "user-1",
  role: "user",
  content: "What is the refund policy?",
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
  created_at: "2026-07-12T00:00:00.000Z",
  citations: [],
};

const assistantMessage: ConversationMessage = {
  ...userMessage,
  id: "assistant-1",
  role: "assistant",
  content: "I do not have enough grounded context to answer.",
  sequence_number: 2,
  answer_state: "fallback",
  model_key: "mock-default",
  provider_key: "mock",
  provider_model_name: "mock-local",
  prompt_key: "grounded_rag_answer",
  prompt_version: 1,
  prompt_hash: "hash",
  execution_id: "exec-1",
  input_tokens: 12,
  output_tokens: 8,
  total_tokens: 20,
  estimated_cost: "0.00010000",
  latency_ms: 33,
  finish_reason: "stop",
  citations: item.citations,
};

const detail: ReviewItemDetail = { item, conversation_context: [userMessage, assistantMessage] };

describe("review queue components", () => {
  it("renders review list rows with distinct states and review status", () => {
    render(<ReviewList items={[item, { ...item, assistant_message_id: "assistant-2", answer_state: "failed", error_code: "provider_timeout", review_status: "knowledge_gap" }, { ...item, assistant_message_id: "assistant-3", answer_state: "low_confidence", review_status: "dismissed" }]} />);

    expect(screen.getAllByText("What is the refund policy?").length).toBe(3);
    expect(screen.getByText("Fallback")).toBeTruthy();
    expect(screen.getByText("Failed")).toBeTruthy();
    expect(screen.getByText("Low confidence")).toBeTruthy();
    expect(screen.getByText("Knowledge gap")).toBeTruthy();
    expect(screen.getByText("Dismissed")).toBeTruthy();
  });

  it("renders labelled filters and review pagination query state", async () => {
    const user = userEvent.setup();
    render(<ReviewFilters answerState="fallback" reviewStatus="open" channel="dashboard_test" limit={20} />);

    const answerState = screen.getByLabelText("Answer state") as HTMLSelectElement;
    const reviewStatus = screen.getByLabelText("Review status") as HTMLSelectElement;
    await user.selectOptions(answerState, "failed");
    await user.selectOptions(reviewStatus, "knowledge_gap");

    expect(answerState.value).toBe("failed");
    expect(reviewStatus.value).toBe("knowledge_gap");
    expect(screen.getByRole("button", { name: "Apply review filters" })).toBeTruthy();

    render(<ReviewPaginationControls basePath="/review/unanswered" answerState="failed" reviewStatus="knowledge_gap" channel="api" limit={10} offset={10} hasNext />);
    expect(screen.getByRole("link", { name: "Next" }).getAttribute("href")).toBe("/review/unanswered?answer_state=failed&review_status=knowledge_gap&channel=api&limit=10&offset=20");
  });

  it("renders status badges with non-colour text", () => {
    render(<ReviewStatusBadge status="knowledge_gap" />);

    expect(screen.getByText("Knowledge gap")).toBeTruthy();
  });

  it("renders review detail question, answer, citations, context, and allowed metadata", () => {
    render(<ReviewDetail detail={detail} session={session} canUpdate />);

    expect(screen.getByRole("heading", { name: "What is the refund policy?" })).toBeTruthy();
    expect(screen.getAllByText("I do not have enough grounded context to answer.").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("[1] Refund Guide").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Execution metadata")).toBeTruthy();
    expect(screen.queryByText("rendered prompt")).toBeNull();
    expect(screen.queryByText("secret")).toBeNull();
  });

  it("disables update controls for viewers", () => {
    render(<ReviewDecisionForm session={{ ...session, role: "viewer" }} item={item} canUpdate={false} />);

    expect(screen.getByText("Viewers can inspect review items but cannot change review status.")).toBeTruthy();
    for (const button of screen.getAllByRole("button")) {
      expect(button.hasAttribute("disabled")).toBe(true);
    }
  });

  it("lets an admin submit a review status update with keyboard-accessible controls", async () => {
    const user = userEvent.setup();
    const updated = { ...item, review_status: "knowledge_gap", reviewer_note: "Add a refund article." };
    const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: updated }), { status: 200 }));
    vi.stubGlobal("fetch", mock);
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
    render(<ReviewDecisionForm session={session} item={item} canUpdate />);

    await user.type(screen.getByLabelText("Reviewer note"), "Add a refund article.");
    await user.click(screen.getByRole("button", { name: "Mark knowledge gap" }));

    expect(mock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(String(mock.mock.calls[0][1].body))).toEqual({
      review_status: "knowledge_gap",
      reviewer_note: "Add a refund article.",
    });
    expect(await screen.findByText("Knowledge gap")).toBeTruthy();
  });

  it("maps API errors in the decision form", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "denied" }), { status: 403 })));
    render(<ReviewDecisionForm session={session} item={item} canUpdate />);

    await user.click(screen.getByRole("button", { name: "Mark reviewed" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("This development user does not have access to the selected workspace.")).toBeTruthy();
  });

  it("keeps citations under the flagged assistant context message", () => {
    render(<ReviewDetail detail={detail} session={session} canUpdate />);

    const context = screen.getByRole("heading", { name: "Nearby messages" }).closest("section");
    expect(context).toBeTruthy();
    expect(within(context as HTMLElement).getByText("[1] Refund Guide")).toBeTruthy();
  });
});
