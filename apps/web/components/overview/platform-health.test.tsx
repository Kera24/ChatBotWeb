import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { OverviewData } from "../../lib/api/overview";
import type { WidgetDetail } from "../../lib/api/widgets";
import { derivePlatformHealth, PlatformHealthBadge, PlatformHealthPanel } from "./platform-health";

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

const baseData: OverviewData = { documents: [], conversations: [], widgets: [], reviewItems: [], reviewTotal: 0 };

describe("derivePlatformHealth", () => {
  it("returns no-assistants when the workspace has no assistants", () => {
    const health = derivePlatformHealth(baseData, []);
    expect(health.key).toBe("no-assistants");
  });

  it("returns document-failures when documents have failed", () => {
    const data: OverviewData = { ...baseData, documents: [{ id: "d1", organisation_id: "o", workspace_id: "w", title: "Doc", source_type: "pdf", source_key: null, status: "failed", category: null, visibility: "workspace", created_by_user_id: null, active_document_version_id: null, metadata_json: null, archived_at: null, expires_at: null, deleted_at: null, created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z" }] };
    const health = derivePlatformHealth(data, [buildAssistant()]);
    expect(health.key).toBe("document-failures");
    expect(health.tone).toBe("danger");
  });

  it("returns review-backlog when there are open knowledge gaps and nothing else is wrong", () => {
    const data: OverviewData = { ...baseData, reviewTotal: 4 };
    const health = derivePlatformHealth(data, [buildAssistant()]);
    expect(health.key).toBe("review-backlog");
  });

  it("returns unpublished-assistants when no assistant is published", () => {
    const health = derivePlatformHealth(baseData, [buildAssistant({ publication_status: "draft" })]);
    expect(health.key).toBe("unpublished-assistants");
  });

  it("returns setup-incomplete when an assistant has no knowledge assigned", () => {
    const assistant = buildAssistant();
    const noKnowledge = { ...assistant, draft: assistant.draft ? { ...assistant.draft, configuration: { ...assistant.draft.configuration, knowledge_scope_json: [] } } : null };
    const health = derivePlatformHealth(baseData, [noKnowledge]);
    expect(health.key).toBe("setup-incomplete");
  });

  it("returns knowledge-processing when documents are processing and nothing else is wrong", () => {
    const data: OverviewData = { ...baseData, documents: [{ id: "d1", organisation_id: "o", workspace_id: "w", title: "Doc", source_type: "pdf", source_key: null, status: "processing", category: null, visibility: "workspace", created_by_user_id: null, active_document_version_id: null, metadata_json: null, archived_at: null, expires_at: null, deleted_at: null, created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z" }] };
    const health = derivePlatformHealth(data, [buildAssistant()]);
    expect(health.key).toBe("knowledge-processing");
  });

  it("returns healthy when nothing is wrong", () => {
    const health = derivePlatformHealth(baseData, [buildAssistant()]);
    expect(health.key).toBe("healthy");
    expect(health.tone).toBe("success");
  });

  it("returns attention-required with a danger tone when multiple issues co-occur including failures", () => {
    const data: OverviewData = {
      ...baseData,
      reviewTotal: 2,
      documents: [{ id: "d1", organisation_id: "o", workspace_id: "w", title: "Doc", source_type: "pdf", source_key: null, status: "failed", category: null, visibility: "workspace", created_by_user_id: null, active_document_version_id: null, metadata_json: null, archived_at: null, expires_at: null, deleted_at: null, created_at: "2026-01-01T00:00:00.000Z", updated_at: "2026-01-01T00:00:00.000Z" }],
    };
    const health = derivePlatformHealth(data, [buildAssistant()]);
    expect(health.key).toBe("attention-required");
    expect(health.tone).toBe("danger");
  });
});

describe("PlatformHealthBadge / PlatformHealthPanel", () => {
  it("communicates health via icon, label, and text, not colour alone", () => {
    const health = derivePlatformHealth(baseData, [buildAssistant()]);
    render(<PlatformHealthBadge health={health} />);
    expect(screen.getByRole("status")).toHaveAccessibleName(/Platform health: Healthy/);
    expect(screen.getByText("Healthy")).toBeTruthy();
  });

  it("renders the health panel with a descriptive explanation", () => {
    const health = derivePlatformHealth(baseData, []);
    render(<PlatformHealthPanel health={health} />);
    expect(screen.getByRole("heading", { name: "Operational status" })).toBeTruthy();
    expect(screen.getByText(/Create your first assistant/)).toBeTruthy();
  });
});
