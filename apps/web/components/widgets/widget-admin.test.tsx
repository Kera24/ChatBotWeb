import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, render, userEvent, waitFor } from "../../test/test-utils";

import { WidgetCreateForm } from "./widget-create-form";
import { WidgetDetailClient } from "./widget-detail-client";
import { WidgetList } from "./widget-status";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import type { WidgetDetail, WidgetEmbedMetadata, WidgetOrigin, WidgetRevisionDetail, WidgetSupportedSdkVersionsResponse } from "../../lib/api/widgets";
import * as widgetApi from "../../lib/api/widgets";

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
    updateWidgetDraft: vi.fn(),
    getWidgetDraft: vi.fn(),
    listWidgetOrigins: vi.fn(),
    addWidgetOrigin: vi.fn(),
    removeWidgetOrigin: vi.fn(),
    getWidgetEmbed: vi.fn(),
    updateWidgetEmbedPreference: vi.fn(),
    rotateWidgetPublicKey: vi.fn(),
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
});

function renderDetail() {
  return render(
    <WidgetDetailClient
      session={session}
      initialWidget={widget}
      initialDraft={draft}
      initialOrigins={[origin]}
      initialEmbed={embed}
      sdkVersions={sdkVersions}
    />,
  );
}


