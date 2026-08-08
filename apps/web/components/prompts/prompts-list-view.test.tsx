import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import type { PromptTemplate } from "../../lib/api/prompts";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { PromptsListView } from "./prompts-list-view";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

function buildTemplate(overrides: Partial<PromptTemplate> = {}): PromptTemplate {
  return {
    id: "template-1",
    organisation_id: null,
    workspace_id: null,
    layer: "platform_core",
    name: "Platform Core Policy",
    description: null,
    is_platform_immutable: true,
    content_visibility: "summary_only",
    ...overrides,
  };
}

describe("PromptsListView", () => {
  it("lists templates with layer badges", () => {
    render(<PromptsListView session={session} templates={[buildTemplate()]} canManage={false} />);
    expect(screen.getByText("Platform Core Policy")).toBeTruthy();
    expect(screen.getByText("platform core")).toBeTruthy();
  });

  it("hides the create-template form for viewers", () => {
    render(<PromptsListView session={session} templates={[]} canManage={false} />);
    expect(screen.queryByRole("button", { name: /Create template/ })).toBeNull();
  });

  it("shows an empty state when there are no templates yet", () => {
    render(<PromptsListView session={session} templates={[]} canManage={false} />);
    expect(screen.getByText("No prompt templates yet")).toBeTruthy();
  });

  it("creates a new workspace template via POST", async () => {
    const user = userEvent.setup();
    const created = buildTemplate({ id: "template-2", layer: "assistant_persona_tone", name: "Support Persona", is_platform_immutable: false, content_visibility: "full" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data: created }), { status: 201 })));
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");

    render(<PromptsListView session={session} templates={[]} canManage />);

    await user.type(screen.getByLabelText("Name"), "Support Persona");
    await user.click(screen.getByRole("button", { name: /Create template/ }));

    expect(await screen.findByText("Support Persona")).toBeTruthy();
  });

  it("requires a name before creating a template", async () => {
    const user = userEvent.setup();
    render(<PromptsListView session={session} templates={[]} canManage />);
    await user.click(screen.getByRole("button", { name: /Create template/ }));
    expect(await screen.findByText(/Enter a name/)).toBeTruthy();
  });
});
