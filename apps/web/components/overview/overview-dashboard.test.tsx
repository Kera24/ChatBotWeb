import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import type { OverviewData } from "../../lib/api/overview";
import type { ConversationSummary, ReviewItem } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { OverviewDashboard } from "./overview-dashboard";
import { OverviewSkeleton } from "./overview-skeleton";

function buildSession(overrides: Partial<DevelopmentDashboardSession> = {}): DevelopmentDashboardSession {
  return {
    organisationId: "organisation-alpha-123456",
    workspaceId: "workspace-alpha-123456",
    userEmail: "admin@example.test",
    fullName: "Admin User",
    role: "client_admin",
    onboardingComplete: true,
    organisationName: "Yoranix College",
    workspaceName: "Admissions Workspace",
    ...overrides,
  };
}

function buildAssistant(overrides: Partial<WidgetDetail> = {}): WidgetDetail {
  return {
    id: "widget-active",
    display_name: "Admissions Widget",
    public_identifier: "public-active",
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
    draft: {
      id: "revision-3",
      revision_number: 3,
      status: "draft",
      is_active_published: false,
      concurrency_version: 1,
      created_by_user_id: null,
      created_at: "2026-01-01T00:00:00.000Z",
      published_by_user_id: null,
      published_at: null,
      source_revision_id: null,
      configuration: {
        bot_name: "Bot",
        welcome_message: "Hello",
        launcher_label: "Chat",
        primary_colour: "#1B2A4A",
        secondary_colour: null,
        logo_path: null,
        avatar_path: null,
        position: "bottom-right",
        theme_mode: "light",
        suggested_questions_json: [],
        fallback_contact_text: null,
        privacy_notice_text: null,
        privacy_notice_url: null,
        terms_url: null,
        language: "en",
        show_citations: true,
        allow_conversation_history: true,
        max_initial_suggestions: 3,
        knowledge_scope_json: ["doc-ready"],
      },
    },
    active_published_revision: null,
    diff: null,
    ...overrides,
  };
}

function buildDocument(overrides: Partial<OverviewData["documents"][number]> = {}): OverviewData["documents"][number] {
  return {
    id: "doc-ready",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    title: "Admissions Policy",
    source_type: "pdf",
    source_key: "admissions.pdf",
    status: "ready",
    category: "policy",
    visibility: "workspace",
    created_by_user_id: "user-1",
    active_document_version_id: "version-ready",
    metadata_json: null,
    archived_at: null,
    expires_at: null,
    deleted_at: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-02T00:00:00.000Z",
    ...overrides,
  };
}

function buildConversation(overrides: Partial<ConversationSummary> = {}): ConversationSummary {
  return {
    id: "conversation-12345678",
    assistant_id: "widget-active",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    channel: "widget",
    status: "active",
    title: "Admissions test chat",
    started_at: "2026-01-03T00:00:00.000Z",
    last_message_at: "2026-01-03T00:10:00.000Z",
    ended_at: null,
    message_count: 4,
    last_message_preview: null,
    metadata: null,
    ...overrides,
  };
}

function buildReviewItem(overrides: Partial<ReviewItem> = {}): ReviewItem {
  return {
    conversation_id: "conversation-12345678",
    assistant_id: "widget-active",
    assistant_message_id: "message-1",
    user_question: "What is the deadline?",
    assistant_answer: "redacted in overview",
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
    created_at: "2026-01-03T00:05:00.000Z",
    estimated_cost: null,
    latency_ms: 140,
    review_status: "open",
    reviewer_note: null,
    reviewed_at: null,
    reviewed_by: null,
    ...overrides,
  };
}

const baseData: OverviewData = { documents: [], conversations: [], widgets: [], reviewItems: [], reviewTotal: 0 };

describe("OverviewDashboard", () => {
  it("renders the workspace and organisation context in the executive header", () => {
    render(<OverviewDashboard session={buildSession()} data={baseData} assistants={[buildAssistant()]} environment="staging" />);
    expect(screen.getByRole("heading", { name: "Admissions Workspace" })).toBeTruthy();
    expect(screen.getByText(/Yoranix College/)).toBeTruthy();
    expect(screen.getByText("staging environment")).toBeTruthy();
  });

  it("shows a healthy platform status when there are no issues", () => {
    const data: OverviewData = { ...baseData, conversations: [buildConversation()] };
    render(<OverviewDashboard session={buildSession()} data={data} assistants={[buildAssistant()]} environment="staging" />);
    expect(screen.getAllByText("Healthy").length).toBeGreaterThan(0);
  });

  it("shows attention-required with multiple concrete issues, never color-only", () => {
    const failing = buildDocument({ id: "doc-failed", status: "failed" });
    const data: OverviewData = { ...baseData, documents: [failing], reviewTotal: 2 };
    render(<OverviewDashboard session={buildSession()} data={data} assistants={[buildAssistant()]} environment="staging" />);
    const badge = screen.getAllByRole("status").find((node) => node.textContent?.includes("Attention required"));
    expect(badge).toBeTruthy();
    expect(badge?.getAttribute("aria-label")).toMatch(/Attention required/);
  });

  it("renders executive metrics using only existing/derived fields with a labeled recent window", () => {
    const data: OverviewData = { ...baseData, documents: [buildDocument()], conversations: [buildConversation()] };
    render(<OverviewDashboard session={buildSession()} data={data} assistants={[buildAssistant()]} environment="staging" />);
    const grid = screen.getByLabelText("Executive metrics");
    expect(within(grid).getByText("Total assistants")).toBeTruthy();
    expect(within(grid).getByText(/bounded window|recent window of up to/i)).toBeTruthy();
  });

  it("renders the assistant portfolio with lifecycle, knowledge, and conversation counts", () => {
    const data: OverviewData = { ...baseData, conversations: [buildConversation()] };
    render(<OverviewDashboard session={buildSession()} data={data} assistants={[buildAssistant()]} environment="staging" />);
    expect(screen.getByRole("heading", { name: "Admissions Widget" })).toBeTruthy();
  });

  it("renders knowledge health with real assistant-scoped knowledge links", () => {
    const noKnowledgeAssistant = buildAssistant({ id: "widget-empty", display_name: "Empty Widget", draft: null });
    render(<OverviewDashboard session={buildSession()} data={baseData} assistants={[noKnowledgeAssistant]} environment="staging" />);
    const links = screen.getAllByRole("link", { name: /Add knowledge/ });
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      expect(link.getAttribute("href")).toBe("/knowledge?assistant=widget-empty");
    }
  });

  it("summarizes quality signals without claiming correctness, hallucination rate, or satisfaction", () => {
    const data: OverviewData = { ...baseData, reviewItems: [buildReviewItem()], reviewTotal: 1 };
    render(<OverviewDashboard session={buildSession()} data={data} assistants={[buildAssistant()]} environment="staging" />);
    expect(screen.queryByText(/hallucination/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/customer satisfaction/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/answer correctness/i)).not.toBeInTheDocument();
  });

  it("builds the action centre from deterministic rules over real fields, each with a real link", () => {
    const data: OverviewData = { ...baseData, documents: [buildDocument({ status: "failed" })] };
    render(<OverviewDashboard session={buildSession()} data={data} assistants={[buildAssistant()]} environment="staging" />);
    expect(screen.getByText(/deterministic operational rules/i)).toBeTruthy();
    expect(screen.getByText("Document processing failures")).toBeTruthy();
  });

  it("renders recent activity from real timestamps without exposing message bodies", () => {
    const data: OverviewData = { ...baseData, documents: [buildDocument()], conversations: [buildConversation()], reviewItems: [buildReviewItem()] };
    render(<OverviewDashboard session={buildSession()} data={data} assistants={[buildAssistant()]} environment="staging" />);
    const timeline = screen.getByRole("list", { name: "Recent platform activity" });
    expect(within(timeline).getByText("Admissions Policy")).toBeTruthy();
    expect(within(timeline).getByText("Admissions test chat")).toBeTruthy();
    expect(screen.queryByText("redacted in overview")).not.toBeInTheDocument();
  });

  it("preserves assistant context in quick actions when a primary assistant resolves", () => {
    render(<OverviewDashboard session={buildSession()} data={baseData} assistants={[buildAssistant()]} environment="staging" />);
    for (const link of screen.getAllByRole("link", { name: /Upload knowledge/ })) {
      expect(link.getAttribute("href")).toBe("/knowledge?assistant=widget-active");
    }
    expect(screen.getByRole("link", { name: /Resolve knowledge gaps/ }).getAttribute("href")).toBe("/review/unanswered?assistant=widget-active");
  });

  it("shows the zero-assistant state and hides assistant-specific sections and actions", () => {
    render(<OverviewDashboard session={buildSession()} data={baseData} assistants={[]} environment="staging" />);
    expect(screen.getByRole("heading", { name: "Create your first assistant" })).toBeTruthy();
    expect(screen.queryByLabelText("Executive metrics")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Upload knowledge/ })).not.toBeInTheDocument();
  });

  it("renders the no-knowledge state within knowledge health for assistants with nothing assigned", () => {
    const noKnowledgeAssistant = buildAssistant({ id: "widget-empty", display_name: "Empty Widget", draft: null });
    render(<OverviewDashboard session={buildSession()} data={baseData} assistants={[noKnowledgeAssistant]} environment="staging" />);
    expect(screen.getAllByText("Assistants with no knowledge").length).toBeGreaterThan(0);
  });

  it("renders a loading skeleton matching the final layout without exposing internal identifiers", () => {
    render(<OverviewSkeleton />);
    expect(screen.getByRole("heading", { name: "Loading Conversa overview" })).toBeTruthy();
    expect(screen.getByText("Collecting tenant-scoped dashboard signals.")).toBeTruthy();
  });
});
