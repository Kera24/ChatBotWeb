import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { ConversationSummary } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { AssistantPortfolio, buildAssistantPortfolio, NoAssistantsPortfolioState } from "./assistant-portfolio";

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
        knowledge_scope_json: ["doc-1", "doc-2"],
      },
    },
    active_published_revision: null,
    diff: null,
    ...overrides,
  };
}

const conversations: ConversationSummary[] = [
  { id: "c1", assistant_id: "assistant-1", organisation_id: "o", workspace_id: "w", channel: "widget", status: "active", title: null, started_at: "2026-01-01T00:00:00.000Z", last_message_at: null, ended_at: null, message_count: 1, last_message_preview: null, metadata: null },
];

describe("buildAssistantPortfolio", () => {
  it("computes knowledge count, conversation count, and lifecycle for each assistant", () => {
    const cards = buildAssistantPortfolio([buildAssistant()], conversations);
    expect(cards).toHaveLength(1);
    expect(cards[0].knowledgeCount).toBe(2);
    expect(cards[0].conversationCount).toBe(1);
    expect(cards[0].lifecycle).toBe("Published");
    expect(cards[0].actionRequired).toBeNull();
  });

  it("flags assistants with no knowledge as needing an action", () => {
    const assistant = buildAssistant();
    const noKnowledge = { ...assistant, draft: assistant.draft ? { ...assistant.draft, configuration: { ...assistant.draft.configuration, knowledge_scope_json: [] } } : null };
    const cards = buildAssistantPortfolio([noKnowledge], []);
    expect(cards[0].actionRequired).toMatch(/Add knowledge/);
    expect(cards[0].primaryAction.href).toBe("/knowledge?assistant=assistant-1");
  });

  it("sorts assistants by most recently updated first", () => {
    const older = buildAssistant({ id: "older", updated_at: "2026-01-01T00:00:00.000Z" });
    const newer = buildAssistant({ id: "newer", updated_at: "2026-01-20T00:00:00.000Z" });
    const cards = buildAssistantPortfolio([older, newer], []);
    expect(cards[0].id).toBe("newer");
  });
});

describe("AssistantPortfolio", () => {
  it("renders assistant cards with lifecycle badge, knowledge, conversations, and a primary action", () => {
    const cards = buildAssistantPortfolio([buildAssistant()], conversations);
    render(<AssistantPortfolio cards={cards} totalAssistants={1} />);

    expect(screen.getByRole("heading", { name: "Admissions Assistant" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "View all assistants" }).getAttribute("href")).toBe("/dashboard");
  });

  it("shows a note and directory link when more assistants exist than are displayed", () => {
    const many = Array.from({ length: 8 }, (_, index) => buildAssistant({ id: `assistant-${index}`, display_name: `Assistant ${index}` }));
    const cards = buildAssistantPortfolio(many, []);
    render(<AssistantPortfolio cards={cards} totalAssistants={8} />);
    expect(screen.getByText(/Showing 6 of 8 assistants/)).toBeTruthy();
  });
});

describe("NoAssistantsPortfolioState", () => {
  it("guides the user to create an assistant", () => {
    render(<NoAssistantsPortfolioState />);
    expect(screen.getByRole("link", { name: /Create assistant/ }).getAttribute("href")).toBe("/assistants/new");
  });
});
