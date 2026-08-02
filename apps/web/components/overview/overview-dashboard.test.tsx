import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OverviewDashboard, OverviewSkeleton } from "./overview-dashboard";
import type { OverviewData } from "../../lib/api/overview";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "organisation-alpha-123456",
  workspaceId: "workspace-alpha-123456",
  userEmail: "admin@example.test",
  role: "client_admin",
};

function minutesAgo(minutes: number) {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

const overviewData: OverviewData = {
  documents: [
    {
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
      created_at: minutesAgo(120),
      updated_at: minutesAgo(5),
    },
    {
      id: "doc-failed",
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      title: "Financial Aid FAQ",
      source_type: "txt",
      source_key: "aid.txt",
      status: "failed",
      category: "faq",
      visibility: "workspace",
      created_by_user_id: "user-1",
      active_document_version_id: "version-failed",
      metadata_json: null,
      archived_at: null,
      expires_at: null,
      deleted_at: null,
      created_at: minutesAgo(240),
      updated_at: minutesAgo(90),
    },
    {
      id: "doc-processing",
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      title: "Orientation Guide",
      source_type: "pdf",
      source_key: "orientation.pdf",
      status: "processing",
      category: "guide",
      visibility: "workspace",
      created_by_user_id: "user-1",
      active_document_version_id: "version-processing",
      metadata_json: null,
      archived_at: null,
      expires_at: null,
      deleted_at: null,
      created_at: minutesAgo(70),
      updated_at: minutesAgo(65),
    },
  ],
  conversations: [
    {
      id: "conversation-12345678",
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      channel: "dashboard_test",
      status: "active",
      title: "Admissions test chat",
      started_at: new Date().toISOString(),
      last_message_at: minutesAgo(3),
      ended_at: null,
      message_count: 4,
      last_message_preview: null,
      metadata: null,
    },
  ],
  widgets: [
    {
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
      created_at: minutesAgo(600),
      updated_at: minutesAgo(8),
    },
    {
      id: "widget-draft",
      display_name: "Draft Widget",
      public_identifier: "public-draft",
      public_credential_id: "credential-2",
      publication_status: "draft",
      active_revision_number: null,
      active_published_revision_id: null,
      draft_revision_id: "revision-1",
      draft_dirty: true,
      operational_status: "disabled",
      pilot_status: null,
      release_channel: "staging",
      created_at: minutesAgo(700),
      updated_at: minutesAgo(60),
    },
  ],
  reviewItems: [
    {
      conversation_id: "conversation-12345678",
      assistant_message_id: "message-1",
      user_question: null,
      assistant_answer: "redacted in overview",
      answer_state: "fallback",
      error_code: null,
      channel: "dashboard_test",
      conversation_status: "active",
      model_key: null,
      provider_key: null,
      prompt_key: null,
      prompt_version: null,
      citation_count: 0,
      citations: [],
      created_at: minutesAgo(4),
      estimated_cost: null,
      latency_ms: null,
      review_status: "open",
      reviewer_note: null,
      reviewed_at: null,
      reviewed_by: null,
    },
  ],
  reviewTotal: 3,
};

describe("OverviewDashboard", () => {
  it("renders Yoranix summary cards from existing module data", () => {
    render(<OverviewDashboard session={session} data={overviewData} environment="development" />);

    expect(screen.getByRole("heading", { name: /operational view of the ai knowledge platform/i })).toBeInTheDocument();
    expect(screen.getByText("Total documents")).toBeInTheDocument();
    expect(screen.getByText("Ready documents")).toBeInTheDocument();
    expect(screen.getByText("Open knowledge gaps")).toBeInTheDocument();
    expect(screen.getByText("Active widgets")).toBeInTheDocument();
    expect(screen.getByText("1/2")).toBeInTheDocument();
  });

  it("renders AI health and actionable alerts", () => {
    render(<OverviewDashboard session={session} data={overviewData} environment="development" />);

    expect(screen.getByText("Attention required")).toBeInTheDocument();
    expect(screen.getByText("Document processing")).toBeInTheDocument();
    expect(screen.getByText("Failed document processing")).toBeInTheDocument();
    expect(screen.getByText("Documents may be stalled")).toBeInTheDocument();
    expect(screen.getByText("Knowledge review backlog")).toBeInTheDocument();
    expect(screen.getByText("Inactive widget configuration")).toBeInTheDocument();
  });

  it("renders recent activity without exposing message bodies", () => {
    render(<OverviewDashboard session={session} data={overviewData} environment="development" />);

    expect(screen.getByText("Admissions Policy")).toBeInTheDocument();
    expect(screen.getByText("Admissions test chat")).toBeInTheDocument();
    expect(screen.getByText("Knowledge gap flagged")).toBeInTheDocument();
    expect(screen.queryByText("redacted in overview")).not.toBeInTheDocument();
  });

  it("renders quick action navigation", () => {
    render(<OverviewDashboard session={session} data={overviewData} environment="development" />);

    const quickActions = screen.getByRole("heading", { name: "Move to the right operational surface" }).closest("section");
    expect(quickActions).not.toBeNull();
    expect(within(quickActions as HTMLElement).getByRole("link", { name: "Upload document" }).getAttribute("href")).toBe("/knowledge");
    expect(within(quickActions as HTMLElement).getByRole("link", { name: "Open chatbot" }).getAttribute("href")).toBe("/chatbot");
    expect(within(quickActions as HTMLElement).getByRole("link", { name: "Review knowledge gaps" }).getAttribute("href")).toBe("/review/unanswered");
  });

  it("renders empty and all-clear states", () => {
    render(<OverviewDashboard session={session} data={{ documents: [], conversations: [], widgets: [], reviewItems: [], reviewTotal: 0 }} environment="test" />);

    expect(screen.getByText("No recent activity")).toBeInTheDocument();
    expect(screen.getByText("No actionable alerts")).toBeInTheDocument();
    expect(screen.getByText("No ready documents are visible from the document lifecycle.")).toBeInTheDocument();
  });

  it("renders the loading skeleton", () => {
    render(<OverviewSkeleton />);

    expect(screen.getByRole("heading", { name: "Loading Yoranix overview" })).toBeInTheDocument();
    expect(screen.getByText("Collecting tenant-scoped dashboard signals.")).toBeInTheDocument();
  });
});
