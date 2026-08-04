import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalyticsDashboard, AnalyticsNoAssistantState, AnalyticsSkeleton, calculateAnalyticsMetrics } from "./analytics-dashboard";
import type { AnalyticsData } from "../../lib/api/analytics";
import type { ConversationMessage } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";

const ASSISTANT_ID = "widget-1";

function minutesAgo(minutes: number) {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

const assistantWithCitation: ConversationMessage = {
  id: "assistant-1",
  assistant_id: ASSISTANT_ID,
  role: "assistant",
  content: "Answer body should not appear in analytics",
  sequence_number: 2,
  answer_state: "answered",
  model_key: "model",
  provider_key: "provider",
  provider_model_name: "provider-model",
  prompt_key: "prompt",
  prompt_version: 1,
  prompt_hash: "hash",
  execution_id: "execution",
  input_tokens: 40,
  output_tokens: 20,
  total_tokens: 60,
  estimated_cost: null,
  latency_ms: 100,
  finish_reason: "stop",
  error_code: null,
  created_at: minutesAgo(4),
  citations: [{
    id: "citation-1",
    assistant_id: ASSISTANT_ID,
    citation_index: 1,
    chunk_id: "chunk-1",
    document_id: "doc-1",
    document_version_id: "version-1",
    similarity_score: 0.8,
    source_title: "Admissions Policy",
    source_type: "pdf",
    page_number: 1,
    section_title: "Admissions",
    quoted_text: "quoted text",
    created_at: minutesAgo(4),
  }],
};

const fallbackAssistant: ConversationMessage = {
  ...assistantWithCitation,
  id: "assistant-2",
  answer_state: "fallback",
  total_tokens: 30,
  latency_ms: 300,
  citations: [],
};

const userMessage: ConversationMessage = {
  ...assistantWithCitation,
  id: "user-1",
  role: "user",
  content: "What scholarships are available?",
  citations: [],
};

const data: AnalyticsData = {
  filters: { assistantId: ASSISTANT_ID, conversation_channel: "widget", document_status: "failed" },
  documents: [
    {
      id: "doc-1",
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      title: "Admissions Policy",
      source_type: "pdf",
      source_key: "admissions.pdf",
      status: "ready",
      category: "policy",
      visibility: "workspace",
      created_by_user_id: "user-1",
      active_document_version_id: "version-1",
      metadata_json: null,
      archived_at: null,
      expires_at: null,
      deleted_at: null,
      created_at: minutesAgo(1000),
      updated_at: minutesAgo(10),
    },
    {
      id: "doc-2",
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      title: "Failed Aid FAQ",
      source_type: "txt",
      source_key: "aid.txt",
      status: "failed",
      category: "faq",
      visibility: "workspace",
      created_by_user_id: "user-1",
      active_document_version_id: "version-2",
      metadata_json: null,
      archived_at: null,
      expires_at: null,
      deleted_at: null,
      created_at: minutesAgo(900),
      updated_at: minutesAgo(70),
    },
    {
      id: "doc-3",
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      title: "Never Cited Handbook",
      source_type: "pdf",
      source_key: "handbook.pdf",
      status: "ready",
      category: "policy",
      visibility: "workspace",
      created_by_user_id: "user-1",
      active_document_version_id: "version-3",
      metadata_json: null,
      archived_at: null,
      expires_at: null,
      deleted_at: null,
      created_at: minutesAgo(1000),
      updated_at: minutesAgo(5),
    },
  ],
  conversations: [
    {
      id: "conversation-1",
      assistant_id: ASSISTANT_ID,
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      channel: "widget",
      status: "active",
      title: "Widget conversation",
      started_at: minutesAgo(50),
      last_message_at: minutesAgo(4),
      ended_at: null,
      message_count: 4,
      last_message_preview: "Preview should not drive analytics",
      metadata: null,
    },
    {
      id: "conversation-2",
      assistant_id: ASSISTANT_ID,
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      channel: "dashboard_test",
      status: "completed",
      title: "Dashboard test",
      started_at: minutesAgo(1500),
      last_message_at: minutesAgo(1490),
      ended_at: null,
      message_count: 2,
      last_message_preview: null,
      metadata: null,
    },
  ],
  conversationDetails: [
    {
      id: "conversation-1",
      assistant_id: ASSISTANT_ID,
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      channel: "widget",
      status: "active",
      title: "Widget conversation",
      started_at: minutesAgo(50),
      last_message_at: minutesAgo(4),
      ended_at: null,
      created_at: minutesAgo(50),
      updated_at: minutesAgo(4),
      metadata: null,
      messages: [userMessage, assistantWithCitation, fallbackAssistant],
    },
  ],
  widgets: [],
  reviewItems: [
    {
      conversation_id: "conversation-1",
      assistant_id: ASSISTANT_ID,
      assistant_message_id: "assistant-2",
      user_question: "What scholarships are available?",
      assistant_answer: "Do not show answer body",
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
      created_at: minutesAgo(4),
      estimated_cost: null,
      latency_ms: 300,
      review_status: "open",
      reviewer_note: null,
      reviewed_at: null,
      reviewed_by: null,
    },
  ],
  reviewTotal: 3,
  recentWindowLimit: 100,
  detailSampleLimit: 25,
};

function buildAssistant(overrides: Partial<WidgetDetail> = {}): WidgetDetail {
  return {
    id: ASSISTANT_ID,
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
    created_at: minutesAgo(2000),
    updated_at: minutesAgo(15),
    draft: null,
    active_published_revision: null,
    diff: null,
    ...overrides,
  };
}

describe("AnalyticsDashboard", () => {
  it("renders the executive header with assistant identity and quick links", () => {
    render(<AnalyticsDashboard data={data} assistant={buildAssistant()} />);

    expect(screen.getByRole("heading", { name: "Admissions Assistant" })).toBeInTheDocument();
    expect(screen.getByLabelText("Status: Published")).toBeInTheDocument();
    expect(screen.getByText(/Knowledge 2\/3 ready/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Knowledge/ })).toHaveAttribute("href", `/knowledge?assistant=${ASSISTANT_ID}`);
    expect(screen.getByRole("link", { name: /Playground/ })).toHaveAttribute("href", `/assistants/${ASSISTANT_ID}?tab=playground&assistant=${ASSISTANT_ID}`);
    expect(screen.getByRole("link", { name: /Conversations/ })).toHaveAttribute("href", `/conversations?assistant=${ASSISTANT_ID}`);
    expect(screen.getByRole("link", { name: /Widget/ })).toHaveAttribute("href", `/assistants/${ASSISTANT_ID}?tab=widget&assistant=${ASSISTANT_ID}`);
  });

  it("shows an archived-assistant notice when the assistant is archived", () => {
    render(<AnalyticsDashboard data={data} assistant={buildAssistant({ operational_status: "archived" })} />);
    expect(screen.getByRole("status")).toHaveTextContent(/archived/i);
  });

  it("renders usage metrics, filters, and the data-scope notice", () => {
    render(<AnalyticsDashboard data={data} assistant={buildAssistant()} />);

    const metricGrid = screen.getByLabelText("Usage metrics");
    expect(within(metricGrid).getByText("Conversations")).toBeInTheDocument();
    expect(within(metricGrid).getByText("Knowledge gaps")).toBeInTheDocument();
    expect(screen.getByLabelText("Analytics data limitations")).toBeInTheDocument();
    expect(screen.getByLabelText("Analytics filters")).toBeInTheDocument();
    expect((screen.getByLabelText("Source") as HTMLSelectElement).value).toBe("widget");
  });

  it("renders response quality metrics from sampled conversation details without leaking answer bodies", () => {
    render(<AnalyticsDashboard data={data} assistant={buildAssistant()} />);

    expect(screen.getByText("Citation rate")).toBeInTheDocument();
    expect(screen.getAllByText("Average latency").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Answer body should not appear in analytics")).not.toBeInTheDocument();
    expect(screen.queryByText("Do not show answer body")).not.toBeInTheDocument();
  });

  it("renders trend, distribution, and document/question panels", () => {
    render(<AnalyticsDashboard data={data} assistant={buildAssistant()} />);

    expect(screen.getByLabelText("Conversations by day")).toBeInTheDocument();
    expect(screen.getByLabelText("Document status distribution")).toBeInTheDocument();
    expect(screen.getByLabelText("Assistant answer-state distribution")).toBeInTheDocument();
    const topDocuments = screen.getByLabelText("Most referenced documents");
    expect(within(topDocuments).getByText("Admissions Policy")).toBeInTheDocument();
    const topDocumentsPanel = screen.getByRole("region", { name: "Top documents" });
    expect(within(topDocumentsPanel).getByText(/Never Cited Handbook/)).toBeInTheDocument();
    expect(screen.getByLabelText("Most frequently asked questions")).toBeInTheDocument();
  });

  it("renders AI insights and a prioritised recommendation panel", () => {
    render(<AnalyticsDashboard data={data} assistant={buildAssistant()} />);

    const insightsPanel = screen.getByRole("region", { name: "Signals worth reviewing" });
    expect(within(insightsPanel).getByText("Knowledge review backlog")).toBeInTheDocument();
    expect(within(insightsPanel).getByText("Document processing failures")).toBeInTheDocument();
    const recommendations = screen.getByRole("complementary", { name: "Recommended actions" });
    expect(within(recommendations).getByText("Next best steps")).toBeInTheDocument();
  });

  it("shows an assistant-healthy recommendation when no negative signals are present", () => {
    const healthyMessage: ConversationMessage = { ...assistantWithCitation, created_at: minutesAgo(2) };
    const healthyData: AnalyticsData = {
      filters: {},
      documents: [data.documents[0]],
      conversations: [{ ...data.conversations[0], last_message_at: minutesAgo(2) }],
      conversationDetails: [{ ...data.conversationDetails[0], messages: [healthyMessage] }],
      widgets: [],
      reviewItems: [],
      reviewTotal: 0,
      recentWindowLimit: 100,
      detailSampleLimit: 25,
    };
    render(<AnalyticsDashboard data={healthyData} assistant={buildAssistant()} />);

    const recommendations = screen.getByRole("complementary", { name: "Recommended actions" });
    expect(within(recommendations).getByText("Assistant healthy")).toBeInTheDocument();
  });

  it("renders the recent activity timeline", () => {
    render(<AnalyticsDashboard data={data} assistant={buildAssistant()} />);
    expect(screen.getByText("Timeline")).toBeInTheDocument();
    expect(screen.getByText("Widget conversation")).toBeInTheDocument();
  });

  it("renders a dedicated empty state when there is no analytics signal yet", () => {
    const emptyData: AnalyticsData = { filters: {}, documents: [], conversations: [], conversationDetails: [], widgets: [], reviewItems: [], reviewTotal: 0, recentWindowLimit: 100, detailSampleLimit: 25 };
    render(<AnalyticsDashboard data={emptyData} assistant={buildAssistant()} />);

    expect(screen.getByText("No analytics yet")).toBeInTheDocument();
    expect(screen.queryByLabelText("Usage metrics")).not.toBeInTheDocument();
  });

  it("calculates metric summaries from existing fields only", () => {
    const metrics = calculateAnalyticsMetrics(data);

    expect(metrics.assistantMessageCount).toBe(2);
    expect(metrics.citedResponses).toBe(1);
    expect(metrics.citationCoverageLabel).toBe("50%");
    expect(metrics.fallbackRateLabel).toBe("50%");
    expect(metrics.averageLatencyLabel).toBe("200 ms");
    expect(metrics.knowledgeCoverageLabel).toBe("67%");
    expect(metrics.resolutionRateLabel).toBe("50%");
  });

  it("renders the loading skeleton", () => {
    render(<AnalyticsSkeleton />);
    expect(screen.getByRole("heading", { name: "Loading Conversa analytics" })).toBeInTheDocument();
  });
});

describe("AnalyticsNoAssistantState", () => {
  it("prompts the user to select an assistant", () => {
    render(<AnalyticsNoAssistantState />);
    expect(screen.getByText("No assistant selected")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to My Assistants" })).toHaveAttribute("href", "/dashboard");
  });
});
