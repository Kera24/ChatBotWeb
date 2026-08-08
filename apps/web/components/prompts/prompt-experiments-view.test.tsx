import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import type { PromptExperiment, PromptVersion } from "../../lib/api/prompts";
import type { WidgetSummary } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { PromptExperimentsView } from "./prompt-experiments-view";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "owner@example.test",
  role: "org_owner",
};

function buildVersion(overrides: Partial<PromptVersion> = {}): PromptVersion {
  return {
    id: "version-1",
    template_id: "template-1",
    version_number: 1,
    status: "approved",
    author_user_id: "user-1",
    change_notes: null,
    parent_version_id: null,
    approved_at: null,
    approved_by_user_id: null,
    published_at: null,
    created_at: "2026-08-01T00:00:00.000Z",
    updated_at: "2026-08-01T00:00:00.000Z",
    content_visibility: "full",
    content: "Be warm.",
    checksum: "abc",
    variables_schema_json: [],
    ...overrides,
  };
}

function buildExperiment(overrides: Partial<PromptExperiment> = {}): PromptExperiment {
  return {
    id: "experiment-1",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    widget_id: "widget-1",
    layer: "assistant_persona_tone",
    control_version_id: "version-1",
    candidate_version_id: "version-2",
    traffic_allocation_percentage: 10,
    start_at: null,
    end_at: null,
    max_duration_hours: null,
    status: "draft",
    success_criteria_json: null,
    evaluation_dataset_id: null,
    candidate_gate_run_id: null,
    safety_gate_state: "pending",
    created_by_user_id: "user-1",
    created_at: "2026-08-01T00:00:00.000Z",
    ...overrides,
  };
}

const widgets: WidgetSummary[] = [
  { id: "widget-1", display_name: "Support Bot", public_identifier: "support-bot", public_credential_id: "cred-1", publication_status: "published", active_revision_number: 1, active_published_revision_id: "rev-1", draft_revision_id: null, draft_dirty: false, operational_status: "enabled" } as WidgetSummary,
];

describe("PromptExperimentsView", () => {
  it("shows the create-experiment form for a manager", () => {
    render(<PromptExperimentsView session={session} templateId="template-1" layer="assistant_persona_tone" versions={[buildVersion()]} widgets={widgets} canManage isSuperAdmin={false} />);
    expect(screen.getByRole("heading", { name: /Set up a control vs\. candidate test/ })).toBeTruthy();
  });

  it("hides the create-experiment form for a viewer", () => {
    render(<PromptExperimentsView session={session} templateId="template-1" layer="assistant_persona_tone" versions={[buildVersion()]} widgets={widgets} canManage={false} isSuperAdmin={false} />);
    expect(screen.queryByRole("heading", { name: /Set up a control vs\. candidate test/ })).toBeNull();
  });

  it("warns that platform_core experiments require super admin", () => {
    render(<PromptExperimentsView session={session} templateId="template-1" layer="platform_core" versions={[buildVersion()]} widgets={widgets} canManage isSuperAdmin />);
    expect(screen.getByText(/require super admin and a passed safety gate/)).toBeTruthy();
  });

  it("creates a new experiment via POST", async () => {
    const user = userEvent.setup();
    const created = buildExperiment();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: created }), { status: 201 })));
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");

    render(<PromptExperimentsView session={session} templateId="template-1" layer="assistant_persona_tone" versions={[buildVersion(), buildVersion({ id: "version-2", version_number: 2 })]} widgets={widgets} canManage isSuperAdmin={false} />);

    await user.selectOptions(screen.getByLabelText("Assistant"), "widget-1");
    await user.click(screen.getByRole("button", { name: /Create experiment/ }));

    expect(await screen.findByText(/requires a passed evaluation gate/)).toBeTruthy();
  });

  it("shows a start button only for draft experiments", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: buildExperiment() }), { status: 201 })));
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");

    render(<PromptExperimentsView session={session} templateId="template-1" layer="assistant_persona_tone" versions={[buildVersion(), buildVersion({ id: "version-2", version_number: 2 })]} widgets={widgets} canManage isSuperAdmin={false} />);
    await user.selectOptions(screen.getByLabelText("Assistant"), "widget-1");
    await user.click(screen.getByRole("button", { name: /Create experiment/ }));
    await screen.findByText(/requires a passed evaluation gate/);

    expect(screen.getByRole("button", { name: /^Start$/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Kill switch/ })).toBeNull();
  });
});
