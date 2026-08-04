import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { DocumentRecord } from "../../lib/api/documents";
import type { WidgetDetail } from "../../lib/api/widgets";
import { KnowledgeHealth } from "./knowledge-health";

function buildDocument(overrides: Partial<DocumentRecord> = {}): DocumentRecord {
  return {
    id: "doc-1",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    title: "Admissions Policy",
    source_type: "pdf",
    source_key: null,
    status: "ready",
    category: null,
    visibility: "workspace",
    created_by_user_id: null,
    active_document_version_id: null,
    metadata_json: null,
    archived_at: null,
    expires_at: null,
    deleted_at: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-02T00:00:00.000Z",
    ...overrides,
  };
}

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
    draft: null,
    active_published_revision: null,
    diff: null,
    ...overrides,
  };
}

describe("KnowledgeHealth", () => {
  it("renders document lifecycle counts and the latest update", () => {
    render(<KnowledgeHealth documents={[buildDocument({ status: "ready" }), buildDocument({ id: "doc-2", status: "failed" })]} assistants={[buildAssistant()]} />);

    expect(screen.getByRole("link", { name: /Open knowledge base/ }).getAttribute("href")).toBe("/knowledge");
    expect(screen.getByText("2")).toBeTruthy();
  });

  it("lists recent uploads", () => {
    render(<KnowledgeHealth documents={[buildDocument()]} assistants={[buildAssistant()]} />);
    expect(screen.getByText("Recent uploads")).toBeTruthy();
    expect(screen.getByText("Admissions Policy")).toBeTruthy();
  });

  it("lists assistants with no knowledge and links to their assistant-scoped knowledge page", () => {
    render(<KnowledgeHealth documents={[]} assistants={[buildAssistant()]} />);
    expect(screen.getByText("Assistants with no knowledge")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Add knowledge/ }).getAttribute("href")).toBe("/knowledge?assistant=assistant-1");
  });

  it("omits the no-knowledge list when every assistant has knowledge assigned", () => {
    const assistant = buildAssistant({
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
    });
    render(<KnowledgeHealth documents={[]} assistants={[assistant]} />);
    expect(screen.queryByText("Assistants with no knowledge")).not.toBeInTheDocument();
  });
});
