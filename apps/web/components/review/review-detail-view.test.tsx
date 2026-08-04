import { describe, expect, it } from "vitest";

import { render, screen, userEvent, within } from "../../test/test-utils";
import type { ConversationMessage, ReviewItemDetail } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { ReviewDetailView } from "./review-detail-view";

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

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

const userMessage: ConversationMessage = {
  id: "user-1",
  assistant_id: "assistant-1",
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
  citations: [
    { id: "citation-1", assistant_id: "assistant-1", citation_index: 1, chunk_id: "chunk-1", document_id: "document-1", document_version_id: "version-1", similarity_score: "0.9", source_title: "Refund Guide", source_type: "txt", page_number: null, section_title: "Policy", quoted_text: "Refunds are processed within five days.", created_at: "2026-07-12T00:00:00.000Z" },
  ],
};

const detail: ReviewItemDetail = {
  item: {
    conversation_id: "conversation-1",
    assistant_id: "assistant-1",
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
    citations: assistantMessage.citations,
    created_at: "2026-07-12T00:00:00.000Z",
    estimated_cost: "0.00010000",
    latency_ms: 33,
    review_status: "open",
    reviewer_note: null,
    reviewed_at: null,
    reviewed_by: null,
  },
  conversation_context: [userMessage, assistantMessage],
};

describe("ReviewDetailView", () => {
  it("renders review detail question, answer, citations, context, and allowed metadata", () => {
    render(<ReviewDetailView detail={detail} assistant={buildAssistant()} session={session} canUpdate />);

    expect(screen.getByRole("heading", { name: "What is the refund policy?" })).toBeTruthy();
    expect(screen.getAllByText("I do not have enough grounded context to answer.").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Execution metadata")).toBeTruthy();
    expect(screen.queryByText("rendered prompt")).toBeNull();
    expect(screen.queryByText("secret")).toBeNull();
  });

  it("shows the knowledge improvement panel with rule-based guidance", () => {
    render(<ReviewDetailView detail={detail} assistant={buildAssistant()} session={session} canUpdate />);
    expect(screen.getByRole("heading", { name: "Guidance from existing signals" })).toBeTruthy();
    expect(screen.getByText("Fallback answer")).toBeTruthy();
  });

  it("shows the quality panel with review/answer state and assistant/workspace context", () => {
    render(<ReviewDetailView detail={detail} assistant={buildAssistant()} session={session} canUpdate />);
    const panel = screen.getByRole("complementary", { name: "Quality & metadata" });
    expect(within(panel).getByText("Admissions Assistant")).toBeTruthy();
    expect(within(panel).getByText("workspace-1")).toBeTruthy();
  });

  it("opens a citation drawer with full source detail from the Sources section", async () => {
    const user = userEvent.setup();
    render(<ReviewDetailView detail={detail} assistant={buildAssistant()} session={session} canUpdate />);

    const sourcesPanel = screen.getByRole("region", { name: "Citations attached to this answer" });
    await user.click(within(sourcesPanel).getByRole("button", { name: /Refund Guide/ }));

    expect(screen.getByRole("dialog", { name: /Refund Guide/ })).toBeTruthy();
    expect(screen.getByText("Refunds are processed within five days.")).toBeTruthy();
  });

  it("keeps citations under the flagged assistant context message in the transcript", () => {
    render(<ReviewDetailView detail={detail} assistant={buildAssistant()} session={session} canUpdate />);

    const context = screen.getByRole("heading", { name: "Nearby messages" }).closest("section");
    expect(context).toBeTruthy();
    expect(within(context as HTMLElement).getByRole("button", { name: /Refund Guide/ })).toBeTruthy();
  });

  it("shows an archived-assistant notice when the assistant is archived", () => {
    render(<ReviewDetailView detail={detail} assistant={buildAssistant({ operational_status: "archived" })} session={session} canUpdate />);
    expect(screen.getByRole("status")).toHaveTextContent(/archived/i);
  });
});
