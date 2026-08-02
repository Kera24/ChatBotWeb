import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalyticsDashboard, AnalyticsSkeleton, calculateAnalyticsMetrics } from "./analytics-dashboard";
import type { AnalyticsData } from "../../lib/api/analytics";
import type { ConversationMessage } from "../../lib/api/types";

function minutesAgo(minutes: number) {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

const assistantWithCitation: ConversationMessage = {
  id: "assistant-1",
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

const data: AnalyticsData = {
  filters: { conversation_channel: "widget", document_status: "failed" },
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
  ],
  conversations: [
    {
      id: "conversation-1",
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
      messages: [assistantWithCitation, fallbackAssistant],
    },
  ],
  widgets: [
    {
      id: "widget-1",
      display_name: "Admissions Widget",
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
      created_at: minutesAgo(1000),
      updated_at: minutesAgo(20),
    },
    {
      id: "widget-2",
      display_name: "Draft Widget",
      public_identifier: "public-2",
      public_credential_id: "credential-2",
      publication_status: "draft",
      active_revision_number: null,
      active_published_revision_id: null,
      draft_revision_id: "revision-1",
      draft_dirty: true,
      operational_status: "disabled",
      pilot_status: null,
      release_channel: "staging",
      created_at: minutesAgo(1000),
      updated_at: minutesAgo(90),
    },
  ],
  reviewItems: [
    {
      conversation_id: "conversation-1",
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

describe("AnalyticsDashboard", () => {
  it("renders usage metrics, filters, and partial data limitation", () => {
    render(<AnalyticsDashboard data={data} />);

    expect(screen.getByRole("heading", { name: /operational analytics from live workspace data/i })).toBeInTheDocument();
    expect(screen.getByText("Recent conversations")).toBeInTheDocument();
    expect(screen.getByText("Open knowledge gaps")).toBeInTheDocument();
    expect(screen.getByText("Data scope")).toBeInTheDocument();
    expect(screen.getByLabelText("Analytics filters")).toBeInTheDocument();
    expect((screen.getByLabelText("Source") as HTMLSelectElement).value).toBe("widget");
  });

  it("renders response quality from detailed conversation fields without answer bodies", () => {
    render(<AnalyticsDashboard data={data} />);

    expect(screen.getByText("Citation coverage")).toBeInTheDocument();
    expect(screen.getAllByText("50%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Average latency")).toBeInTheDocument();
    expect(screen.getByText("200 ms")).toBeInTheDocument();
    expect(screen.queryByText("Answer body should not appear in analytics")).not.toBeInTheDocument();
    expect(screen.queryByText("Do not show answer body")).not.toBeInTheDocument();
  });

  it("renders operational charts and tables with navigation", () => {
    render(<AnalyticsDashboard data={data} />);

    expect(screen.getByLabelText("Conversation source distribution")).toBeInTheDocument();
    expect(screen.getByLabelText("Document status distribution")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "What scholarships are available?" }).getAttribute("href")).toBe("/review/unanswered/assistant-2");
    expect(screen.getByRole("link", { name: "Admissions Widget" }).getAttribute("href")).toBe("/widgets/widget-1");
    expect(screen.getByRole("link", { name: "Open conversations" }).getAttribute("href")).toBe("/conversations");
  });

  it("renders actionable insights from supported data", () => {
    render(<AnalyticsDashboard data={data} />);

    expect(screen.getByText("Knowledge review backlog")).toBeInTheDocument();
    expect(screen.getByText("Document processing failures")).toBeInTheDocument();
    expect(screen.getByText("Inactive widgets")).toBeInTheDocument();
    expect(screen.getByText("Elevated fallback rate")).toBeInTheDocument();
  });

  it("renders empty states and omits unsupported correctness metrics", () => {
    render(<AnalyticsDashboard data={{ filters: {}, documents: [], conversations: [], conversationDetails: [], widgets: [], reviewItems: [], reviewTotal: 0, recentWindowLimit: 100, detailSampleLimit: 25 }} />);

    expect(screen.getByText("No conversation volume")).toBeInTheDocument();
    expect(screen.getByText("No action required")).toBeInTheDocument();
    expect(screen.queryByText(/AI-generated recommendation/i)).not.toBeInTheDocument();
  });

  it("calculates metric summaries from existing fields", () => {
    const metrics = calculateAnalyticsMetrics(data);

    expect(metrics.assistantMessageCount).toBe(2);
    expect(metrics.citedResponses).toBe(1);
    expect(metrics.citationCoverageLabel).toBe("50%");
    expect(metrics.fallbackRateLabel).toBe("50%");
    expect(metrics.averageLatencyLabel).toBe("200 ms");
    expect(metrics.totalTokensLabel).toBe("90");
  });

  it("renders the loading skeleton", () => {
    render(<AnalyticsSkeleton />);

    expect(screen.getByRole("heading", { name: "Loading Yoranix analytics" })).toBeInTheDocument();
    expect(screen.getByText("Collecting tenant-scoped operational metrics.")).toBeInTheDocument();
  });
});


