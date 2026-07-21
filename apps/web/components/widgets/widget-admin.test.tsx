import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, render, userEvent, waitFor } from "../../test/test-utils";

import { WidgetCreateForm } from "./widget-create-form";
import { WidgetDetailClient } from "./widget-detail-client";
import { WidgetList } from "./widget-status";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import type { WidgetDetail, WidgetEmbedMetadata, WidgetInstallationStatus, WidgetKnowledgeOption, WidgetOrigin, WidgetRevisionDetail, WidgetSupportedSdkVersionsResponse } from "../../lib/api/widgets";
import * as widgetApi from "../../lib/api/widgets";
import { DashboardApiError } from "../../lib/api/errors";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("../../lib/api/widgets", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api/widgets")>();
  return {
    ...actual,
    createWidget: vi.fn(),
    getWidgetDetail: vi.fn(),
    updateWidgetDraft: vi.fn(),
    getWidgetDraft: vi.fn(),
    listWidgetOrigins: vi.fn(),
    addWidgetOrigin: vi.fn(),
    removeWidgetOrigin: vi.fn(),
    getWidgetEmbed: vi.fn(),
    updateWidgetEmbedPreference: vi.fn(),
    rotateWidgetPublicKey: vi.fn(),
    listWidgetKnowledgeOptions: vi.fn(),
    updateWidgetKnowledgeScope: vi.fn(),
    validateWidgetPublish: vi.fn(),
    publishWidget: vi.fn(),
    listWidgetRevisions: vi.fn(),
    getWidgetRevision: vi.fn(),
    rollbackWidget: vi.fn(),
    createWidgetPreviewGrant: vi.fn(),
    getWidgetInstallationStatus: vi.fn(),
  };
});

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

const config = {
  bot_name: "Admissions Assistant",
  welcome_message: "Ask us about admissions.",
  launcher_label: "Ask us",
  primary_colour: "#111827",
  secondary_colour: null,
  logo_path: null,
  avatar_path: null,
  position: "bottom_right",
  theme_mode: "system",
  suggested_questions_json: ["How do I apply?"],
  fallback_contact_text: null,
  privacy_notice_text: null,
  privacy_notice_url: null,
  terms_url: null,
  language: "en",
  show_citations: true,
  allow_conversation_history: true,
  max_initial_suggestions: 1,
  knowledge_scope_json: [],
};

const draft: WidgetRevisionDetail = {
  id: "draft-1",
  revision_number: 1,
  status: "draft",
  is_active_published: false,
  concurrency_version: 3,
  created_by_user_id: "user-1",
  created_at: "2026-07-20T00:00:00.000Z",
  published_by_user_id: null,
  published_at: null,
  source_revision_id: null,
  configuration: config,
};

const widget: WidgetDetail = {
  id: "widget-1",
  display_name: "Admissions Widget",
  public_identifier: "wpk_dev_123456",
  public_credential_id: "credential-1",
  publication_status: "draft",
  active_revision_number: null,
  active_published_revision_id: null,
  draft_revision_id: "draft-1",
  draft_dirty: true,
  operational_status: "enabled",
  pilot_status: "not_approved",
  release_channel: "pilot",
  created_at: "2026-07-20T00:00:00.000Z",
  updated_at: "2026-07-20T00:00:00.000Z",
  draft,
  active_published_revision: null,
  diff: { changed_fields: ["bot_name"], has_published_revision: false },
};

const origin: WidgetOrigin = {
  id: "origin-1",
  origin: "https://example.com",
  scheme: "https",
  hostname: "example.com",
  port: null,
  wildcard_subdomains: false,
  environment: "production",
  active: true,
  created_at: "2026-07-20T00:00:00.000Z",
  updated_at: "2026-07-20T00:00:00.000Z",
};

const embed: WidgetEmbedMetadata = {
  public_key: "wpk_dev_123456",
  public_key_status: "active",
  public_key_created_at: "2026-07-20T00:00:00.000Z",
  public_key_rotated_at: null,
  publication_status: "draft",
  published: false,
  operational_status: "enabled",
  pilot_status: "not_approved",
  release_channel: "pilot",
  version_mode: "managed_major",
  pinned_sdk_version: null,
  selected_sdk_version: "0.1.0-foundation.0",
  selected_loader_path: "/widget-sdk/v1/loader.js",
  protocol_major: 1,
  api_version: "v1",
  sri: null,
  snippet: '<script async src="https://cdn.example.com/widget-sdk/v1/loader.js" data-widget-key="wpk_dev_123456"></script>',
  allowed_origins: [origin],
  active_published_revision_id: null,
  active_revision_number: null,
  readiness: ["unpublished", "pilot_not_enabled"],
  active: false,
  embed_update_required: false,
};

const knowledgeOptions: WidgetKnowledgeOption[] = [
  { id: "doc-1", title: "Admissions handbook", type: "document", readiness: "ready", indexing_status: "completed", updated_at: "2026-07-20T00:00:00.000Z" },
];

const publishedRevision: WidgetRevisionDetail = {
  ...draft,
  id: "published-1",
  revision_number: 0,
  status: "published",
  is_active_published: false,
  concurrency_version: 1,
  published_at: "2026-07-20T00:00:00.000Z",
};

const installationStatus: WidgetInstallationStatus[] = [
  { origin: "https://example.com", status: "observed", last_seen_at: "2026-07-20T01:00:00.000Z", sdk_version: "0.1.0-foundation.0", protocol_major: 1 },
];
const sdkVersions: WidgetSupportedSdkVersionsResponse = {
  recommended: "0.1.0-foundation.0",
  versions: [
    {
      version: "0.1.0-foundation.0",
      sdk_major: 1,
      protocol_major: 1,
      api_version: "v1",
      support_status: "supported",
      immutable_loader_path: "/widget-sdk/v0.1.0-foundation.0/loader.js",
      major_alias_path: "/widget-sdk/v1/loader.js",
      release_channel: "pilot",
      integrity: "sha384-safe",
    },
  ],
};

describe("widget administration frontend", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, "clipboard", { value: { writeText: vi.fn().mockResolvedValue(undefined) }, configurable: true });
    vi.mocked(widgetApi.getWidgetInstallationStatus).mockResolvedValue({ success: true, data: installationStatus });
    vi.mocked(widgetApi.listWidgetRevisions).mockResolvedValue({ success: true, data: [draft, publishedRevision] });
  });

  it("renders widget list without exposing full public key", () => {
    render(<WidgetList widgets={[widget]} />);

    expect(screen.getByRole("link", { name: "Admissions Widget" }).getAttribute("href")).toBe("/widgets/widget-1");
    expect(screen.getByText("Publication: draft")).toBeTruthy();
    expect(screen.queryByText("wpk_dev_123456")).toBeNull();
  });

  it("creates a widget and redirects to the detail route", async () => {
    vi.mocked(widgetApi.createWidget).mockResolvedValue({ success: true, data: widget });
    const user = userEvent.setup();
    render(<WidgetCreateForm session={session} />);

    await user.clear(screen.getByLabelText("Internal widget name"));
    await user.type(screen.getByLabelText("Internal widget name"), "Student Help");
    await user.click(screen.getByRole("button", { name: "Create widget" }));

    await waitFor(() => expect(widgetApi.createWidget).toHaveBeenCalled());
    expect(push).toHaveBeenCalledWith("/widgets/widget-1");
  });

  it("saves appearance draft changes with the current concurrency version", async () => {
    vi.mocked(widgetApi.updateWidgetDraft).mockResolvedValue({ success: true, data: { ...draft, concurrency_version: 4, configuration: { ...config, bot_name: "Campus Bot" } } });
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "Appearance" }));
    await user.clear(screen.getByLabelText("Bot name"));
    await user.type(screen.getByLabelText("Bot name"), "Campus Bot");
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    await waitFor(() => expect(widgetApi.updateWidgetDraft).toHaveBeenCalledWith(session, "widget-1", expect.objectContaining({ bot_name: "Campus Bot", expected_concurrency_version: 3 })));
    expect(await screen.findByText(/Draft saved/)).toBeTruthy();
  });

  it("adds origins and refreshes embed readiness", async () => {
    const nextOrigin = { ...origin, id: "origin-2", origin: "https://second.example" };
    vi.mocked(widgetApi.addWidgetOrigin).mockResolvedValue({ success: true, data: nextOrigin });
    vi.mocked(widgetApi.listWidgetOrigins).mockResolvedValue({ success: true, data: [origin, nextOrigin] });
    vi.mocked(widgetApi.getWidgetEmbed).mockResolvedValue({ success: true, data: { ...embed, allowed_origins: [origin, nextOrigin] } });
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "Domains" }));
    await user.clear(screen.getByLabelText("Allowed origin"));
    await user.type(screen.getByLabelText("Allowed origin"), "https://second.example");
    await user.click(screen.getByRole("button", { name: "Add origin" }));

    await waitFor(() => expect(widgetApi.addWidgetOrigin).toHaveBeenCalledWith(session, "widget-1", "https://second.example"));
    expect(await screen.findByText("Allowed domain added. The canonical origin is now authorized by the backend.")).toBeTruthy();
  });

  it("switches to a pinned SDK and keeps the snippet inert", async () => {
    vi.mocked(widgetApi.updateWidgetEmbedPreference).mockResolvedValue({
      success: true,
      data: { ...embed, version_mode: "pinned", pinned_sdk_version: "0.1.0-foundation.0", selected_loader_path: "/widget-sdk/v0.1.0-foundation.0/loader.js", sri: "sha384-safe", snippet: '<script async src="https://cdn.example.com/widget-sdk/v0.1.0-foundation.0/loader.js" data-widget-key="wpk_dev_123456" integrity="sha384-safe" crossorigin="anonymous"></script>' },
    });
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "Embed" }));
    await user.click(screen.getByLabelText("Pinned immutable SDK"));
    await user.click(screen.getByRole("button", { name: "Save embed version" }));

    await waitFor(() => expect(widgetApi.updateWidgetEmbedPreference).toHaveBeenCalledWith(session, "widget-1", { version_mode: "pinned", pinned_sdk_version: "0.1.0-foundation.0" }));
    expect(screen.getByText(/script async/).closest("pre")).toBeTruthy();
    expect(document.querySelector("script[src='https://cdn.example.com/widget-sdk/v1/loader.js']")).toBeNull();
  });

  it("rotates the public key only after confirmation", async () => {
    vi.mocked(widgetApi.rotateWidgetPublicKey).mockResolvedValue({
      success: true,
      data: {
        widget_id: "widget-1",
        public_credential_id: "credential-2",
        public_key: "wpk_dev_rotated",
        public_key_status: "active",
        old_key_revoked: true,
        embed_update_required: true,
        rotated_at: "2026-07-20T01:00:00.000Z",
      },
    });
    vi.mocked(widgetApi.getWidgetEmbed).mockResolvedValue({ success: true, data: { ...embed, public_key: "wpk_dev_rotated", embed_update_required: true, snippet: '<script async src="https://cdn.example.com/widget-sdk/v1/loader.js" data-widget-key="wpk_dev_rotated"></script>' } });
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "Embed" }));
    await user.click(screen.getByRole("button", { name: "Rotate public key" }));
    expect(screen.getByRole("dialog", { name: "Rotate public widget key?" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Rotate key" }));

    await waitFor(() => expect(widgetApi.rotateWidgetPublicKey).toHaveBeenCalledWith(session, "widget-1", "credential-1"));
    expect(await screen.findByText(/Public key rotated/)).toBeTruthy();
    expect(screen.getAllByText(/wpk_dev_rotated/).length).toBeGreaterThanOrEqual(2);
  });
  it("saves tenant-scoped knowledge selections and reports draft-only semantics", async () => {
    vi.mocked(widgetApi.updateWidgetKnowledgeScope).mockResolvedValue({ success: true, data: { ...draft, concurrency_version: 4, configuration: { ...config, knowledge_scope_json: ["doc-1"] } } });
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "Knowledge" }));
    await user.click(screen.getByLabelText(/Admissions handbook/));
    await user.click(screen.getByRole("button", { name: "Save knowledge scope" }));

    await waitFor(() => expect(widgetApi.updateWidgetKnowledgeScope).toHaveBeenCalledWith(session, "widget-1", { document_ids: ["doc-1"], expected_concurrency_version: 3 }));
    expect(await screen.findByText("Knowledge scope saved to the draft. Public retrieval remains unchanged until publish.")).toBeTruthy();
  });

  it("renders draft preview with a sandboxed titled iframe and does not expose the preview token", async () => {
    vi.mocked(widgetApi.createWidgetPreviewGrant).mockResolvedValue({ success: true, data: { preview_token: "wpg_sensitive_preview_token", expires_at: "2026-07-20T02:00:00.000Z", draft_revision_id: "draft-1", configuration: { ...config, bot_name: "Preview Bot" } } });
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "Preview" }));
    await user.click(screen.getByRole("button", { name: "Refresh preview grant" }));

    await waitFor(() => expect(widgetApi.createWidgetPreviewGrant).toHaveBeenCalledWith(session, "widget-1", "draft-1"));
    const iframe = screen.getByTitle("Widget draft preview") as HTMLIFrameElement;
    expect(iframe.getAttribute("sandbox")).toBe("allow-scripts");
    expect(iframe.getAttribute("srcdoc")).toContain("Preview Bot");
    expect(document.body.textContent).not.toContain("wpg_sensitive_preview_token");
    expect(iframe.getAttribute("srcdoc")).not.toContain("wpg_sensitive_preview_token");
  });

  it("surfaces stale draft conflicts without resubmitting local changes", async () => {
    vi.mocked(widgetApi.updateWidgetDraft).mockRejectedValue(new DashboardApiError("conflict", "stale draft", { status: 409 }));
    vi.mocked(widgetApi.getWidgetDraft).mockResolvedValue({ success: true, data: { ...draft, concurrency_version: 9, configuration: { ...config, bot_name: "Server Bot" } } });
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "Appearance" }));
    await user.clear(screen.getByLabelText("Bot name"));
    await user.type(screen.getByLabelText("Bot name"), "Local Bot");
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    expect(await screen.findByText("The saved draft changed before this form was submitted. Reload the latest draft before saving again.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Reload latest draft" }));
    expect(await screen.findByDisplayValue("Server Bot")).toBeTruthy();
    expect(widgetApi.updateWidgetDraft).toHaveBeenCalledTimes(1);
  });

  it("validates and publishes only after explicit confirmation", async () => {
    const publishedWidget = { ...widget, publication_status: "published", active_revision_number: 2, active_published_revision_id: "published-2" };
    const nextDraft = { ...draft, id: "draft-2", revision_number: 3, concurrency_version: 1 };
    vi.mocked(widgetApi.validateWidgetPublish).mockResolvedValue({ success: true, data: { publishable: true, errors: [], warnings: [], diff: { changed_fields: ["bot_name"], has_published_revision: true }, knowledge: knowledgeOptions } });
    vi.mocked(widgetApi.publishWidget).mockResolvedValue({ success: true, data: { widget: publishedWidget, published_revision: { ...draft, id: "published-2", revision_number: 2, status: "published" }, validation_errors: [] } });
    vi.mocked(widgetApi.getWidgetDetail).mockResolvedValue({ success: true, data: publishedWidget });
    vi.mocked(widgetApi.getWidgetDraft).mockResolvedValue({ success: true, data: nextDraft });
    vi.mocked(widgetApi.getWidgetEmbed).mockResolvedValue({ success: true, data: { ...embed, publication_status: "published", published: true, active_published_revision_id: "published-2", active_revision_number: 2 } });
    vi.mocked(widgetApi.listWidgetRevisions).mockResolvedValue({ success: true, data: [nextDraft, publishedRevision] });
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "Publish" }));
    await user.click(screen.getByRole("button", { name: "Validate publish" }));
    expect(await screen.findByText("Ready to publish")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Publish draft" }));
    expect(screen.getByRole("dialog", { name: "Publish draft revision 1?" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(widgetApi.publishWidget).toHaveBeenCalledWith(session, "widget-1", { draft_revision_id: "draft-1", expected_concurrency_version: 3 }));
    expect(await screen.findByText("Draft published. A new draft revision is ready for future edits.")).toBeTruthy();
  });

  it("views revision history and confirms rollback without rewriting history", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(widgetApi.getWidgetRevision).mockResolvedValue({ success: true, data: publishedRevision });
    vi.mocked(widgetApi.rollbackWidget).mockResolvedValue({ success: true, data: { widget, published_revision: { ...publishedRevision, id: "published-rollback", revision_number: 4, source_revision_id: "published-1" }, rolled_back_from_revision_id: "published-1", validation_errors: [] } });
    vi.mocked(widgetApi.getWidgetDetail).mockResolvedValue({ success: true, data: widget });
    vi.mocked(widgetApi.getWidgetDraft).mockResolvedValue({ success: true, data: draft });
    vi.mocked(widgetApi.getWidgetEmbed).mockResolvedValue({ success: true, data: embed });
    vi.mocked(widgetApi.listWidgetRevisions).mockResolvedValue({ success: true, data: [draft, publishedRevision] });
    const user = userEvent.setup();
    renderDetail({ ...widget, publication_status: "published", active_revision_number: 3, active_published_revision_id: "published-current" });

    await user.click(screen.getByRole("tab", { name: "History" }));
    await user.click(screen.getAllByRole("button", { name: "View" })[1]);
    expect(await screen.findByText("Admissions Assistant")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Rollback" }));

    await waitFor(() => expect(widgetApi.rollbackWidget).toHaveBeenCalledWith(session, "widget-1", { target_revision_id: "published-1", expected_active_revision_id: "published-current" }));
    expect(await screen.findByText("Rollback published as a new immutable revision. Historical revisions were not changed.")).toBeTruthy();
  });

  it("shows installation evidence and keeps unsupported SDK versions unavailable", async () => {
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("tab", { name: "Embed" }));

    expect(screen.getByText("Observed means the platform has seen a valid widget configuration request from that allowed origin.")).toBeTruthy();
    expect(screen.getByText(/SDK 0.1.0-foundation.0/)).toBeTruthy();
    expect(screen.queryByText(/latest/)).toBeNull();
    expect(screen.getByRole("radio", { name: "Managed major alias" })).toBeTruthy();
    expect(screen.getByRole("radio", { name: "Pinned immutable SDK" })).toBeTruthy();
  });
});

function renderDetail(initialWidget: WidgetDetail = widget) {
  return render(
    <WidgetDetailClient
      session={session}
      initialWidget={initialWidget}
      initialDraft={draft}
      initialOrigins={[origin]}
      initialEmbed={embed}
      sdkVersions={sdkVersions}
      knowledgeOptions={knowledgeOptions}
      initialRevisions={[draft, publishedRevision]}
      initialInstallationStatus={installationStatus}
    />,
  );
}
