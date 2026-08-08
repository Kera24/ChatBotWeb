import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import type { PromptTemplate, PromptVersion } from "../../lib/api/prompts";
import type { WidgetSummary } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { PromptTemplateDetailView } from "./prompt-template-detail-view";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "owner@example.test",
  role: "org_owner",
};

function buildTemplate(overrides: Partial<PromptTemplate> = {}): PromptTemplate {
  return {
    id: "template-1",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    layer: "assistant_persona_tone",
    name: "Support Persona",
    description: null,
    is_platform_immutable: false,
    content_visibility: "full",
    ...overrides,
  };
}

function buildVersion(overrides: Partial<PromptVersion> = {}): PromptVersion {
  return {
    id: "version-1",
    template_id: "template-1",
    version_number: 1,
    status: "draft",
    author_user_id: "user-1",
    change_notes: "initial",
    parent_version_id: null,
    approved_at: null,
    approved_by_user_id: null,
    published_at: null,
    created_at: "2026-08-01T00:00:00.000Z",
    updated_at: "2026-08-01T00:00:00.000Z",
    content_visibility: "full",
    content: "Be warm and concise.",
    checksum: "abc123",
    variables_schema_json: [],
    ...overrides,
  };
}

const widgets: WidgetSummary[] = [
  {
    id: "widget-1",
    display_name: "Support Bot",
    public_identifier: "support-bot",
    public_credential_id: "cred-1",
    publication_status: "published",
    active_revision_number: 1,
    active_published_revision_id: "rev-1",
    draft_revision_id: null,
    draft_dirty: false,
    operational_status: "enabled",
  } as WidgetSummary,
];

describe("PromptTemplateDetailView", () => {
  it("renders the layer badge and version content", () => {
    render(<PromptTemplateDetailView session={session} template={buildTemplate()} versions={[buildVersion()]} widgets={widgets} canManage={false} isSuperAdmin={false} />);
    expect(screen.getByText("assistant persona tone")).toBeTruthy();
    expect(screen.getByText("Be warm and concise.")).toBeTruthy();
  });

  it("hides platform-immutable content from a non-super-admin viewer", () => {
    const template = buildTemplate({ layer: "platform_core", is_platform_immutable: true });
    const version = buildVersion({ content_visibility: "summary_only", content: null, checksum: null });
    render(<PromptTemplateDetailView session={session} template={template} versions={[version]} widgets={widgets} canManage isSuperAdmin={false} />);
    expect(screen.getByText(/Content hidden/)).toBeTruthy();
  });

  it("hides mutation controls for viewers without manage access", () => {
    render(<PromptTemplateDetailView session={session} template={buildTemplate()} versions={[buildVersion()]} widgets={widgets} canManage={false} isSuperAdmin={false} />);
    expect(screen.queryByRole("button", { name: /Move to under evaluation/ })).toBeNull();
  });

  it("only offers the next valid transition for a draft version", () => {
    render(<PromptTemplateDetailView session={session} template={buildTemplate()} versions={[buildVersion({ status: "draft" })]} widgets={widgets} canManage isSuperAdmin={false} />);
    expect(screen.getByRole("button", { name: /Move to under evaluation/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Move to approved/ })).toBeNull();
  });

  it("does not offer deploy for a draft version", () => {
    render(<PromptTemplateDetailView session={session} template={buildTemplate()} versions={[buildVersion({ status: "draft" })]} widgets={widgets} canManage isSuperAdmin={false} />);
    expect(screen.queryByRole("button", { name: /^Deploy$/ })).toBeNull();
  });

  it("offers deploy once a version is approved", () => {
    render(<PromptTemplateDetailView session={session} template={buildTemplate()} versions={[buildVersion({ status: "approved" })]} widgets={widgets} canManage isSuperAdmin={false} />);
    expect(screen.getByRole("button", { name: /^Deploy$/ })).toBeTruthy();
  });

  it("creates a new draft version via POST", async () => {
    const user = userEvent.setup();
    const created = buildVersion({ id: "version-2", version_number: 2, content: "Be extremely formal." });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: created }), { status: 201 })));
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");

    render(<PromptTemplateDetailView session={session} template={buildTemplate()} versions={[]} widgets={widgets} canManage isSuperAdmin={false} />);

    await user.type(screen.getByLabelText("Content"), "Be extremely formal.");
    await user.click(screen.getByRole("button", { name: /Create draft/ }));

    expect(await screen.findByText("Draft v2 created.")).toBeTruthy();
  });

  it("transitions a version's status via POST", async () => {
    const user = userEvent.setup();
    const updated = buildVersion({ status: "under_evaluation" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: updated }), { status: 200 })));
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");

    render(<PromptTemplateDetailView session={session} template={buildTemplate()} versions={[buildVersion({ status: "draft" })]} widgets={widgets} canManage isSuperAdmin={false} />);

    await user.click(screen.getByRole("button", { name: /Move to under evaluation/ }));

    expect(await screen.findByText(/moved to under evaluation/)).toBeTruthy();
  });
});
