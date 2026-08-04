import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { OverviewData } from "../../lib/api/overview";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import type { WidgetDetail } from "../../lib/api/widgets";
import { ActionCentre, buildActionItems } from "./action-centre";

function buildAssistant(overrides: Partial<WidgetDetail> = {}): WidgetDetail {
  return {
    id: "assistant-1",
    display_name: "Admissions Assistant",
    public_identifier: "public-1",
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
        knowledge_scope_json: ["doc-1"],
      },
    },
    active_published_revision: null,
    diff: null,
    ...overrides,
  };
}

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  fullName: "Admin User",
  role: "client_admin",
  onboardingComplete: true,
  organisationName: "Yoranix College",
  workspaceName: "Admissions Workspace",
};

const baseData: OverviewData = { documents: [], conversations: [], widgets: [], reviewItems: [], reviewTotal: 0 };

describe("buildActionItems", () => {
  it("flags incomplete onboarding", () => {
    const items = buildActionItems(baseData, [buildAssistant()], { ...session, onboardingComplete: false });
    expect(items.some((item) => item.id === "onboarding-incomplete")).toBe(true);
  });

  it("flags failed document processing", () => {
    const data: OverviewData = { ...baseData, documents: [{ id: "d1", organisation_id: "o", workspace_id: "w", title: "Doc", source_type: "pdf", source_key: null, status: "failed", category: null, visibility: "workspace", created_by_user_id: null, active_document_version_id: null, metadata_json: null, archived_at: null, expires_at: null, deleted_at: null, created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z" }] };
    const items = buildActionItems(data, [buildAssistant()], session);
    expect(items.some((item) => item.id === "failed-documents")).toBe(true);
  });

  it("flags assistants with no knowledge and links to that assistant's knowledge page", () => {
    const assistant = buildAssistant();
    const noKnowledge = { ...assistant, draft: assistant.draft ? { ...assistant.draft, configuration: { ...assistant.draft.configuration, knowledge_scope_json: [] } } : null };
    const items = buildActionItems(baseData, [noKnowledge], session);
    const item = items.find((entry) => entry.id === "assistants-without-knowledge");
    expect(item?.href).toBe("/knowledge?assistant=assistant-1");
  });

  it("flags unpublished assistants", () => {
    const items = buildActionItems(baseData, [buildAssistant({ publication_status: "draft" })], session);
    expect(items.some((item) => item.id === "unpublished-assistants")).toBe(true);
  });

  it("flags published assistants with unpublished draft changes", () => {
    const items = buildActionItems(baseData, [buildAssistant({ draft_dirty: true })], session);
    expect(items.some((item) => item.id === "unpublished-draft-changes")).toBe(true);
  });

  it("flags an unresolved knowledge gap backlog", () => {
    const items = buildActionItems({ ...baseData, reviewTotal: 3 }, [buildAssistant()], session);
    expect(items.some((item) => item.id === "review-backlog")).toBe(true);
  });

  it("flags inactive assistants with no recent conversations", () => {
    const items = buildActionItems(baseData, [buildAssistant()], session);
    expect(items.some((item) => item.id === "inactive-assistants")).toBe(true);
  });

  it("returns no items when everything is healthy and active", () => {
    const data: OverviewData = { ...baseData, conversations: [{ id: "c1", assistant_id: "assistant-1", organisation_id: "o", workspace_id: "w", channel: "widget", status: "active", title: null, started_at: "2026-01-01T00:00:00.000Z", last_message_at: null, ended_at: null, message_count: 1, last_message_preview: null, metadata: null }] };
    const items = buildActionItems(data, [buildAssistant()], session);
    expect(items).toHaveLength(0);
  });
});

describe("ActionCentre", () => {
  it("labels items as deterministic operational rules, not AI-generated recommendations", () => {
    render(<ActionCentre items={buildActionItems({ ...baseData, reviewTotal: 1 }, [buildAssistant()], session)} />);
    expect(screen.getByText(/deterministic operational rules applied to existing platform data, not AI-generated recommendations/i)).toBeTruthy();
  });

  it("shows a positive empty state when nothing needs attention", () => {
    render(<ActionCentre items={[]} />);
    expect(screen.getByRole("heading", { name: "Nothing needs attention" })).toBeTruthy();
  });

  it("renders each action item with a real link", () => {
    render(<ActionCentre items={[{ id: "test", tone: "warning", title: "Test item", detail: "Detail text", href: "/knowledge" }]} />);
    expect(screen.getByRole("link", { name: /Open/ }).getAttribute("href")).toBe("/knowledge");
  });
});
