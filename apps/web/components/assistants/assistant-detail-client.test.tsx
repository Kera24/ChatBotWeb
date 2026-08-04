import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssistantDetailClient, AssistantDetailErrorState, AssistantDetailSkeleton } from "./assistant-detail-client";
import type { OverviewData } from "../../lib/api/overview";
import type { WidgetDetail, WidgetEmbedMetadata, WidgetInstallationStatus, WidgetKnowledgeOption, WidgetOrigin, WidgetRevisionDetail, WidgetSupportedSdkVersionsResponse } from "../../lib/api/widgets";
import * as widgetApi from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

let currentSearch = "";
const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(currentSearch),
  useRouter: () => ({ push, refresh }),
}));

vi.mock("../chatbot/chatbot-client", () => ({
  ChatbotClient: ({ assistantId }: { assistantId: string }) => <div data-testid="playground">Playground for {assistantId}</div>,
}));

vi.mock("../widgets/widget-detail-client", () => ({
  WidgetDetailClient: () => <div data-testid="widget-builder">Widget builder</div>,
}));

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

const draft: WidgetRevisionDetail = {
  id: "draft-1",
  revision_number: 2,
  status: "draft",
  is_active_published: false,
  concurrency_version: 1,
  created_by_user_id: "user-1",
  created_at: "2026-07-10T00:00:00.000Z",
  published_by_user_id: null,
  published_at: null,
  source_revision_id: null,
  configuration: {
    bot_name: "Admissions Assistant",
    welcome_message: "Answers admissions questions from approved sources.",
    launcher_label: "Ask admissions",
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
    max_initial_suggestions: 3,
    knowledge_scope_json: ["doc-1", "doc-2"],
  },
};

const widget: WidgetDetail = {
  id: "assistant-1",
  display_name: "Admissions Assistant",
  public_identifier: "pk_admissions",
  public_credential_id: "cred-1",
  publication_status: "draft",
  active_revision_number: null,
  active_published_revision_id: null,
  draft_revision_id: "draft-1",
  draft_dirty: false,
  operational_status: "enabled",
  pilot_status: "not_approved",
  release_channel: "pilot",
  created_at: "2026-07-01T00:00:00.000Z",
  updated_at: "2026-07-20T00:00:00.000Z",
  active_published_revision: null,
  diff: null,
  draft,
};

const embed: WidgetEmbedMetadata = {
  public_key: "pk_admissions",
  public_key_status: "active",
  public_key_created_at: "2026-07-01T00:00:00.000Z",
  public_key_rotated_at: null,
  publication_status: "draft",
  published: false,
  operational_status: "enabled",
  pilot_status: "not_approved",
  release_channel: "pilot",
  version_mode: "managed_major",
  pinned_sdk_version: null,
  selected_sdk_version: "0.1.0",
  selected_loader_path: "/loader.js",
  protocol_major: 1,
  api_version: "v1",
  sri: null,
  snippet: "<script></script>",
  allowed_origins: [],
  active_published_revision_id: null,
  active_revision_number: null,
  readiness: ["unpublished"],
  active: false,
  embed_update_required: false,
};

const knowledgeOptions: WidgetKnowledgeOption[] = [
  { id: "doc-1", title: "Admissions Handbook", type: "document", readiness: "ready", indexing_status: "ready", updated_at: "2026-07-19T00:00:00.000Z" },
  { id: "doc-2", title: "Scholarships Guide", type: "document", readiness: "indexing", indexing_status: "processing", updated_at: "2026-07-18T00:00:00.000Z" },
];

const origins: WidgetOrigin[] = [{ id: "origin-1", origin: "https://example.test", scheme: "https", hostname: "example.test", port: null, wildcard_subdomains: false, environment: "development", active: true, created_at: "2026-07-14T00:00:00.000Z", updated_at: "2026-07-14T00:00:00.000Z" }];
const revisions: WidgetRevisionDetail[] = [{ ...draft, id: "published-1", status: "published", revision_number: 1, published_at: "2026-07-15T00:00:00.000Z" }];
const sdkVersions: WidgetSupportedSdkVersionsResponse = { recommended: "0.1.0", versions: [] };
const installationStatus: WidgetInstallationStatus[] = [{ origin: "https://example.test", status: "observed", last_seen_at: "2026-07-21T00:00:00.000Z", sdk_version: "0.1.0", protocol_major: 1 }];

const overviewData: OverviewData = {
  documents: [],
  conversations: [
    { id: "conversation-1", assistant_id: "assistant-1", organisation_id: "org-1", workspace_id: "workspace-1", channel: "dashboard_test", status: "completed", title: "Scholarship question", started_at: "2026-07-22T00:00:00.000Z", last_message_at: "2026-07-22T00:00:00.000Z", ended_at: null, message_count: 2, last_message_preview: "What scholarships exist?", metadata: { assistant_id: "assistant-1" } },
  ],
  widgets: [],
  reviewItems: [
    { conversation_id: "conversation-1", assistant_id: "assistant-1", assistant_message_id: "message-1", user_question: "What scholarships exist?", assistant_answer: "I need more context.", answer_state: "fallback", error_code: null, channel: "dashboard_test", conversation_status: "completed", model_key: "model", provider_key: "provider", prompt_key: "prompt", prompt_version: 1, citation_count: 0, citations: [], created_at: "2026-07-22T00:00:00.000Z", estimated_cost: "0", latency_ms: 120, review_status: "open", reviewer_note: null, reviewed_at: null, reviewed_by: null },
  ],
  reviewTotal: 1,
};

function renderDetail(overrides: Partial<Parameters<typeof AssistantDetailClient>[0]> = {}) {
  return render(<AssistantDetailClient session={session} initialWidget={widget} initialDraft={draft} initialOrigins={origins} initialEmbed={embed} initialSdkVersions={sdkVersions} initialKnowledgeOptions={knowledgeOptions} initialRevisions={revisions} initialInstallationStatus={installationStatus} overviewData={overviewData} {...overrides} />);
}

describe("AssistantDetailClient", () => {
  beforeEach(() => {
    currentSearch = "";
    push.mockClear();
    refresh.mockClear();
    vi.clearAllMocks();
  });

  it("renders the assistant header, lifecycle, primary action, and overview snapshots", () => {
    renderDetail();

    expect(screen.getByRole("heading", { name: "Admissions Assistant" })).toBeInTheDocument();
    expect(screen.getAllByText("Answers admissions questions from approved sources.").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Status: Ready")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Test: Open the authenticated playground" })).toHaveAttribute("href", "/assistants/assistant-1?tab=playground&assistant=assistant-1");
    expect(screen.getByRole("heading", { name: "Operating posture" })).toBeInTheDocument();
    expect(screen.getByText("Assistant-scoped recent window")).toBeInTheDocument();
    expect(screen.getByText(/partial metrics from sampled assistant-scoped windows/i)).toBeInTheDocument();
  });

  it("renders sticky tabs with active state and assistant context", () => {
    currentSearch = "tab=knowledge&assistant=assistant-1";
    renderDetail();

    const tabNav = screen.getByRole("navigation", { name: /assistant sections/i });
    expect(within(tabNav).getByRole("link", { name: /^knowledge$/i })).toHaveAttribute("aria-current", "page");
    expect(within(tabNav).getByRole("link", { name: /^analytics$/i })).toHaveAttribute("href", "/assistants/assistant-1?tab=analytics&assistant=assistant-1");
    expect(screen.getByRole("heading", { name: "Knowledge" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /add knowledge/i })).toHaveAttribute("href", "/knowledge?assistant=assistant-1");
  });

  it("renders setup checklist, quick actions, and recent activity from existing data", () => {
    renderDetail();

    expect(screen.getByRole("heading", { name: "Setup progress" })).toBeInTheDocument();
    expect(screen.getByText("Knowledge uploaded")).toBeInTheDocument();
    const quickActions = screen.getByLabelText("Assistant quick actions");
    expect(within(quickActions).getByRole("link", { name: /open conversations/i })).toHaveAttribute("href", "/conversations?assistant=assistant-1");
    expect(screen.getByRole("heading", { name: "Recent activity" })).toBeInTheDocument();
    expect(screen.getAllByText("Admissions Handbook").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Scholarship question").length).toBeGreaterThan(0);
  });

  it("renders playground and widget tabs without breaking existing embedded functionality", () => {
    currentSearch = "tab=playground&assistant=assistant-1";
    const { rerender } = renderDetail();
    expect(screen.getByTestId("playground")).toHaveTextContent("assistant-1");

    currentSearch = "tab=widget&assistant=assistant-1";
    rerender(<AssistantDetailClient session={session} initialWidget={widget} initialDraft={draft} initialOrigins={origins} initialEmbed={embed} initialSdkVersions={sdkVersions} initialKnowledgeOptions={knowledgeOptions} initialRevisions={revisions} initialInstallationStatus={installationStatus} overviewData={overviewData} />);
    expect(screen.getByTestId("widget-builder")).toBeInTheDocument();
  });

  it("duplicates and archives through existing widget actions", async () => {
    const user = userEvent.setup();
    vi.mocked(widgetApi.duplicateWidget).mockResolvedValue({ success: true, data: { ...widget, id: "assistant-copy" } });
    vi.mocked(widgetApi.archiveWidget).mockResolvedValue({ success: true, data: { ...widget, operational_status: "archived" } });

    renderDetail();
    await user.click(screen.getByRole("button", { name: /more actions for admissions assistant/i }));
    await user.click(screen.getByRole("menuitem", { name: /duplicate admissions assistant/i }));
    await waitFor(() => expect(widgetApi.duplicateWidget).toHaveBeenCalledWith(session, "assistant-1"));
    expect(push).toHaveBeenCalledWith("/assistants/assistant-copy?assistant=assistant-copy");

    await user.click(screen.getByRole("button", { name: /more actions for admissions assistant/i }));
    await user.click(screen.getByRole("menuitem", { name: /archive admissions assistant/i }));
    const dialog = screen.getByRole("dialog", { name: /archive assistant/i });
    await user.click(within(dialog).getByRole("button", { name: /^archive$/i }));
    await waitFor(() => expect(widgetApi.archiveWidget).toHaveBeenCalledWith(session, "assistant-1"));
  });

  it("renders empty, archived, loading, and error states", () => {
    renderDetail({ initialKnowledgeOptions: [], initialDraft: { ...draft, configuration: { ...draft.configuration, knowledge_scope_json: [] } }, overviewData: { ...overviewData, conversations: [], reviewItems: [], reviewTotal: 0 } });
    expect(screen.getByText(/no knowledge sources are assigned yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no conversations recorded/i)).toBeInTheDocument();

    renderDetail({ initialWidget: { ...widget, operational_status: "archived" } });
    expect(screen.getByLabelText("Status: Archived")).toBeInTheDocument();

    render(<AssistantDetailSkeleton />);
    expect(screen.getByLabelText(/loading assistant detail/i)).toBeInTheDocument();

    render(<AssistantDetailErrorState message="Please retry." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Please retry.");
  });
});
