import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { AssistantManagement } from "./assistant-management";
import * as widgetApi from "../../lib/api/widgets";
import type { OverviewData } from "../../lib/api/overview";
import type { WidgetDetail } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

vi.mock("../../lib/api/widgets", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api/widgets")>("../../lib/api/widgets");
  return {
    ...actual,
    duplicateWidget: vi.fn(),
    archiveWidget: vi.fn(),
  };
});

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "owner@example.test",
  fullName: "Owner User",
  role: "org_owner",
  onboardingComplete: true,
  organisationName: "Yoranix Test",
  workspaceName: "Default Workspace",
};

const baseWidget: WidgetDetail = {
  id: "assistant-1",
  display_name: "Admissions Assistant",
  public_identifier: "pk_admissions",
  public_credential_id: "cred-1",
  publication_status: "published",
  active_revision_number: 2,
  active_published_revision_id: "rev-published",
  draft_revision_id: "rev-draft",
  draft_dirty: false,
  operational_status: "enabled",
  pilot_status: "not_approved",
  release_channel: "pilot",
  created_at: "2026-07-01T00:00:00.000Z",
  updated_at: "2026-07-20T00:00:00.000Z",
  active_published_revision: null,
  diff: null,
  draft: {
    id: "rev-draft",
    revision_number: 3,
    status: "draft",
    is_active_published: false,
    concurrency_version: 1,
    created_by_user_id: "user-1",
    created_at: "2026-07-20T00:00:00.000Z",
    published_by_user_id: null,
    published_at: null,
    source_revision_id: "rev-published",
    configuration: {
      bot_name: "Admissions Assistant",
      welcome_message: "Ask admissions questions.",
      launcher_label: "Ask AI",
      primary_colour: "#1B2A4A",
      secondary_colour: null,
      logo_path: null,
      avatar_path: null,
      position: "bottom_right",
      theme_mode: "system",
      suggested_questions_json: [],
      fallback_contact_text: null,
      privacy_notice_text: null,
      privacy_notice_url: null,
      terms_url: null,
      language: "en",
      show_citations: true,
      allow_conversation_history: true,
      max_initial_suggestions: 2,
      knowledge_scope_json: ["doc-1"],
    },
  },
};

const salesWidget: WidgetDetail = {
  ...baseWidget,
  id: "assistant-2",
  display_name: "Sales Assistant",
  public_identifier: "pk_sales",
  publication_status: "draft",
  draft_dirty: true,
  updated_at: "2026-07-10T00:00:00.000Z",
  draft: baseWidget.draft ? { ...baseWidget.draft, id: "sales-draft", configuration: { ...baseWidget.draft.configuration, bot_name: "Sales Assistant", knowledge_scope_json: [] } } : null,
};

const overview: OverviewData = {
  documents: [],
  conversations: [
    {
      id: "conversation-1",
      organisation_id: "org-1",
      workspace_id: "workspace-1",
      channel: "widget",
      status: "completed",
      title: "Admissions",
      started_at: "2026-07-20T00:00:00.000Z",
      last_message_at: "2026-07-20T00:00:00.000Z",
      ended_at: null,
      message_count: 3,
      last_message_preview: "How do I apply?",
      metadata: { widget_id: "assistant-1" },
    },
  ],
  widgets: [],
  reviewItems: [],
  reviewTotal: 0,
};

describe("AssistantManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the first-assistant empty state", () => {
    render(<AssistantManagement session={session} assistants={[]} data={overview} />);
    expect(screen.getByRole("heading", { name: /let's build your first ai assistant/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /create assistant/i })).toHaveAttribute("href", "/assistants/new");
  });

  it("filters assistants by name and status", () => {
    render(<AssistantManagement session={session} assistants={[baseWidget, salesWidget]} data={overview} />);
    expect(screen.getByText("Admissions Assistant")).toBeInTheDocument();
    expect(screen.getByText("Sales Assistant")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/search assistants/i), { target: { value: "sales" } });
    expect(screen.queryByText("Admissions Assistant")).not.toBeInTheDocument();
    expect(screen.getByText("Sales Assistant")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/filter assistants by status/i), { target: { value: "Published" } });
    expect(screen.getByText(/no assistants match/i)).toBeInTheDocument();
  });

  it("duplicates and archives assistants through the widget contract", async () => {
    const copy = { ...baseWidget, id: "assistant-copy", display_name: "Admissions Assistant Copy" };
    vi.mocked(widgetApi.duplicateWidget).mockResolvedValue({ success: true, data: copy });
    vi.mocked(widgetApi.archiveWidget).mockResolvedValue({ success: true, data: { ...baseWidget, operational_status: "archived" } });

    render(<AssistantManagement session={session} assistants={[baseWidget]} data={overview} />);
    fireEvent.click(screen.getByRole("button", { name: /duplicate/i }));
    await waitFor(() => expect(widgetApi.duplicateWidget).toHaveBeenCalledWith(session, "assistant-1"));
    expect(screen.getByText("Admissions Assistant Copy")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: /archive/i })[0]);
    await waitFor(() => expect(widgetApi.archiveWidget).toHaveBeenCalled());
  });
});
