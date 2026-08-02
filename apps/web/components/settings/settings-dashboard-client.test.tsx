import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsDashboardClient, SettingsSkeleton } from "./settings-dashboard-client";
import { DashboardApiError } from "../../lib/api/errors";
import * as settingsApi from "../../lib/api/settings";
import type { WorkspaceSettings } from "../../lib/api/settings";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

vi.mock("../../lib/api/settings");

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

const viewerSession: DevelopmentDashboardSession = { ...session, role: "viewer", userEmail: "viewer@example.test" };

function settings(overrides: Partial<WorkspaceSettings> = {}): WorkspaceSettings {
  return {
    workspace: {
      id: "workspace-1",
      organisation_id: "org-1",
      name: "Admissions Workspace",
      slug: "admissions",
      status: "active",
      default_language: "en",
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-02T00:00:00Z",
    },
    organisation: {
      id: "org-1",
      name: "Yoranix College",
      slug: "yoranix-college",
      status: "active",
      plan_key: "pilot",
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-02T00:00:00Z",
    },
    membership_summary: {
      total: 8,
      active: 7,
      inactive: 1,
      administrators: 2,
    },
    operational: {
      environment: "staging",
      service_name: "chatbotweb-api",
      version: "abc123",
      phase: "controlled-pilot",
      public_widgets_enabled: true,
      public_widget_messages_enabled: true,
      public_widget_pilot_enforcement_enabled: true,
      retrieval_max_context_chunks: 10,
      retrieval_max_context_chars: 12000,
      chunk_size_words: 300,
      chunk_overlap_words: 50,
      embedding_provider: "azure-openai",
      embedding_model: "text-embedding-3-small",
      embedding_dimension: 1536,
      default_ai_provider_key: "azure-openai",
      default_ai_model_key: "gpt-4.1-mini",
      ai_request_timeout_seconds: 30,
    },
    capabilities: {
      editable_fields: ["workspace.name", "workspace.default_language"],
      read_only_fields: ["organisation.name", "workspace.slug"],
      environment_controlled_fields: ["embedding_model", "retrieval_max_context_chunks"],
      secret_managed_fields: ["database_url", "redis_url", "application_insights_connection_string"],
      unsupported_fields: ["provider_secret_editing", "notification_preferences"],
    },
    ...overrides,
  };
}

function envelope(data: WorkspaceSettings) {
  return { success: true, data, meta: {} };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(settingsApi.updateWorkspaceSettings).mockResolvedValue(envelope(settings({ workspace: { ...settings().workspace, name: "Support Workspace", default_language: "en-AU", updated_at: "2026-07-03T00:00:00Z" } })));
});

describe("SettingsDashboardClient", () => {
  it("renders workspace, organisation, operational, and boundary settings", () => {
    render(<SettingsDashboardClient session={session} initialSettings={settings()} />);

    expect(screen.getByRole("heading", { name: "Workspace controls and operational posture" })).toBeInTheDocument();
    expect(screen.getByDisplayValue("Admissions Workspace")).toBeInTheDocument();
    expect(screen.getByText("Yoranix College")).toBeInTheDocument();
    expect(screen.getAllByText("azure-openai")).toHaveLength(2);
    expect(screen.getByText("Widget-owned configuration")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage widget configuration" })).toHaveAttribute("href", "/widgets");
    expect(screen.getByText("database url")).toBeInTheDocument();
    expect(screen.queryByText(/postgres|redis:\/\/|connection string value/i)).not.toBeInTheDocument();
  });

  it("tracks dirty state, resets, and saves supported workspace fields", async () => {
    const user = userEvent.setup();
    render(<SettingsDashboardClient session={session} initialSettings={settings()} />);

    const saveButton = screen.getByRole("button", { name: "Save changes" });
    expect(saveButton).toBeDisabled();

    await user.clear(screen.getByLabelText("Workspace name"));
    await user.type(screen.getByLabelText("Workspace name"), "Support Workspace");
    await user.clear(screen.getByLabelText("Default language"));
    await user.type(screen.getByLabelText("Default language"), "en-AU");
    expect(saveButton).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.getByDisplayValue("Admissions Workspace")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Workspace name"));
    await user.type(screen.getByLabelText("Workspace name"), "Support Workspace");
    await user.clear(screen.getByLabelText("Default language"));
    await user.type(screen.getByLabelText("Default language"), "en-AU");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(settingsApi.updateWorkspaceSettings).toHaveBeenCalledWith(session, { name: "Support Workspace", default_language: "en-AU", expected_updated_at: "2026-07-02T00:00:00Z" }));
    expect(await screen.findByText("Workspace settings saved.")).toBeInTheDocument();
  });

  it("validates fields before saving", async () => {
    const user = userEvent.setup();
    render(<SettingsDashboardClient session={session} initialSettings={settings()} />);

    await user.clear(screen.getByLabelText("Workspace name"));

    expect(screen.getByRole("alert")).toHaveTextContent("Workspace name is required.");
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("renders read-only behaviour for viewers", () => {
    render(<SettingsDashboardClient session={viewerSession} initialSettings={settings()} />);

    expect(screen.getByLabelText("Workspace name")).toBeDisabled();
    expect(screen.getByLabelText("Default language")).toBeDisabled();
    expect(screen.getByText(/only organisation owners and client admins can change workspace fields/i)).toBeInTheDocument();
  });

  it("shows conflict errors from stale saves", async () => {
    const user = userEvent.setup();
    vi.mocked(settingsApi.updateWorkspaceSettings).mockRejectedValue(new DashboardApiError("conflict", "Conflict", { status: 409 }));
    render(<SettingsDashboardClient session={session} initialSettings={settings()} />);

    await user.clear(screen.getByLabelText("Workspace name"));
    await user.type(screen.getByLabelText("Workspace name"), "Changed Workspace");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Reload the page before saving again");
  });

  it("renders loading skeleton", () => {
    render(<SettingsSkeleton />);

    expect(screen.getByRole("heading", { name: "Loading Yoranix settings" })).toBeInTheDocument();
  });
});

