import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { ConversationDetail } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { ConversationDetailView } from "./conversation-detail-view";

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

const conversation: ConversationDetail = {
  id: "conversation-1",
  assistant_id: "assistant-1",
  organisation_id: "org-1",
  workspace_id: "workspace-1",
  channel: "widget",
  status: "active",
  title: "Pricing question",
  started_at: "2026-07-12T01:00:00.000Z",
  last_message_at: "2026-07-12T01:05:00.000Z",
  ended_at: null,
  created_at: "2026-07-12T01:00:00.000Z",
  updated_at: "2026-07-12T01:05:00.000Z",
  metadata: null,
  messages: [
    {
      id: "message-1",
      assistant_id: "assistant-1",
      role: "assistant",
      content: "Grounded answer",
      sequence_number: 1,
      answer_state: "answered",
      model_key: "mock",
      provider_key: "mock",
      provider_model_name: "mock-v1",
      prompt_key: "prompt",
      prompt_version: 1,
      prompt_hash: "hash",
      execution_id: "exec-1",
      input_tokens: 10,
      output_tokens: 10,
      total_tokens: 20,
      estimated_cost: null,
      latency_ms: 90,
      finish_reason: "stop",
      error_code: null,
      created_at: "2026-07-12T01:04:00.000Z",
      citations: [],
    },
  ],
};

describe("ConversationDetailView", () => {
  it("renders the detail header, transcript, and quality panel together", () => {
    render(<ConversationDetailView conversation={conversation} assistant={buildAssistant()} />);

    expect(screen.getByRole("heading", { name: "Pricing question" })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Back to conversations/ }).getAttribute("href")).toBe("/conversations?assistant=assistant-1");
    expect(screen.getByRole("log", { name: "Conversation messages" })).toBeTruthy();
    expect(screen.getByText("Grounded answer")).toBeTruthy();
    expect(screen.getByRole("complementary", { name: "Quality & metadata" })).toBeTruthy();
  });

  it("shows an archived-assistant notice when the assistant is archived", () => {
    render(<ConversationDetailView conversation={conversation} assistant={buildAssistant({ operational_status: "archived" })} />);
    expect(screen.getByRole("status")).toHaveTextContent(/archived/i);
  });
});
