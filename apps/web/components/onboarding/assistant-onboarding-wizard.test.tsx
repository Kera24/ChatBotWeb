import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, render, userEvent, waitFor } from "../../test/test-utils";

import { AssistantOnboardingWizard } from "./assistant-onboarding-wizard";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import * as authApi from "../../lib/api/auth";
import * as chatbotApi from "../../lib/api/chatbot";
import * as documentApi from "../../lib/api/documents";
import * as widgetApi from "../../lib/api/widgets";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("../../lib/api/auth", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api/auth")>()),
  completeOnboarding: vi.fn(),
}));

vi.mock("../../lib/api/widgets", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api/widgets")>()),
  createWidget: vi.fn(),
  updateWidgetKnowledgeScope: vi.fn(),
  addWidgetOrigin: vi.fn(),
  activateWidgetPublicCredential: vi.fn(),
  validateWidgetPublish: vi.fn(),
  publishWidget: vi.fn(),
  getWidgetEmbed: vi.fn(),
}));

vi.mock("../../lib/api/documents", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api/documents")>()),
  uploadDocument: vi.fn(),
  extractDocumentVersion: vi.fn(),
  chunkDocumentVersion: vi.fn(),
  embedDocumentVersion: vi.fn(),
  transitionDocument: vi.fn(),
}));

vi.mock("../../lib/api/chatbot", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api/chatbot")>()),
  answerChatbotQuestion: vi.fn(),
}));

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "owner@example.test",
  fullName: "Owner",
  role: "org_owner",
  onboardingComplete: false,
  organisationName: "Acme",
  workspaceName: "Default workspace",
};

const draft = {
  id: "draft-1",
  revision_number: 1,
  status: "draft",
  is_active_published: false,
  concurrency_version: 1,
  created_by_user_id: "user-1",
  created_at: "2026-08-02T00:00:00.000Z",
  published_by_user_id: null,
  published_at: null,
  source_revision_id: null,
  configuration: {
    bot_name: "Support Assistant",
    welcome_message: "Ask a question.",
    launcher_label: "Ask AI",
    primary_colour: "#1B2A4A",
    secondary_colour: "#F7F5F0",
    logo_path: null,
    avatar_path: null,
    position: "bottom_right",
    theme_mode: "system",
    suggested_questions_json: ["How can you help?"],
    fallback_contact_text: null,
    privacy_notice_text: null,
    privacy_notice_url: null,
    terms_url: null,
    language: "en",
    show_citations: true,
    allow_conversation_history: true,
    max_initial_suggestions: 3,
    knowledge_scope_json: [],
  },
};

const widget = {
  id: "widget-1",
  display_name: "Support Assistant",
  public_identifier: "wpk_live_123",
  public_credential_id: "credential-1",
  publication_status: "draft",
  active_revision_number: null,
  active_published_revision_id: null,
  draft_revision_id: "draft-1",
  draft_dirty: true,
  operational_status: "enabled",
  pilot_status: "not_approved",
  release_channel: "pilot",
  created_at: "2026-08-02T00:00:00.000Z",
  updated_at: "2026-08-02T00:00:00.000Z",
  draft,
  active_published_revision: null,
  diff: { changed_fields: ["bot_name"], has_published_revision: false },
};

const uploadResult = {
  document: {
    id: "doc-1",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    title: "handbook.txt",
    source_type: "txt",
    source_key: "handbook.txt",
    status: "uploaded",
    category: "onboarding",
    visibility: "workspace",
    created_by_user_id: "user-1",
    active_document_version_id: "version-1",
    metadata_json: null,
    archived_at: null,
    expires_at: null,
    deleted_at: null,
    created_at: "2026-08-02T00:00:00.000Z",
    updated_at: "2026-08-02T00:00:00.000Z",
  },
  document_version: {
    id: "version-1",
    organisation_id: "org-1",
    workspace_id: "workspace-1",
    document_id: "doc-1",
    version_number: 1,
    original_file_path: null,
    extracted_text_path: null,
    checksum: "sha256:test",
    processing_status: "pending",
    processing_error: null,
    effective_from: null,
    expires_at: null,
    created_by_user_id: "user-1",
    metadata_json: null,
    created_at: "2026-08-02T00:00:00.000Z",
    updated_at: "2026-08-02T00:00:00.000Z",
  },
};

const embed = {
  public_key: "wpk_live_123",
  public_key_status: "active",
  public_key_created_at: "2026-08-02T00:00:00.000Z",
  public_key_rotated_at: null,
  publication_status: "published",
  published: true,
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
  snippet: '<script async src="https://cdn.example.com/widget-sdk/v1/loader.js" data-widget-key="wpk_live_123"></script>',
  allowed_origins: [],
  active_published_revision_id: "published-1",
  active_revision_number: 2,
  readiness: ["ready"],
  active: true,
  embed_update_required: false,
};

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(navigator, "clipboard", { value: { writeText: vi.fn().mockResolvedValue(undefined) }, configurable: true });
  vi.mocked(widgetApi.createWidget).mockResolvedValue({ success: true, data: widget });
  vi.mocked(documentApi.uploadDocument).mockResolvedValue({ success: true, data: uploadResult });
  vi.mocked(documentApi.extractDocumentVersion).mockResolvedValue({ success: true, data: uploadResult.document_version, meta: { success: true } });
  vi.mocked(documentApi.chunkDocumentVersion).mockResolvedValue({ success: true, data: uploadResult.document_version, meta: { success: true } });
  vi.mocked(documentApi.embedDocumentVersion).mockResolvedValue({ success: true, data: uploadResult.document_version, meta: { success: true } });
  vi.mocked(documentApi.transitionDocument).mockResolvedValue({ success: true, data: { ...uploadResult.document, status: "ready" }, meta: { success: true } });
  vi.mocked(widgetApi.updateWidgetKnowledgeScope).mockResolvedValue({ success: true, data: { ...draft, concurrency_version: 2, configuration: { ...draft.configuration, knowledge_scope_json: ["doc-1"] } } });
  vi.mocked(chatbotApi.answerChatbotQuestion).mockResolvedValue({ success: true, data: {
    conversation_id: "conversation-1",
    user_message_id: "user-message-1",
    assistant_message_id: "assistant-message-1",
    answer: "The assistant can answer from the uploaded handbook.",
    answer_state: "answered",
    citations: [{ citation_index: 1, chunk_id: "chunk-1", document_id: "doc-1", document_version_id: "version-1", source_title: "handbook.txt", source_type: "txt", page_number: null, section_title: null, similarity_score: 0.93, quoted_text: "Handbook excerpt" }],
    retrieved_chunk_count: 1,
    provider_key: "test",
    model_key: "test-model",
    provider_model_name: "test-model",
    prompt_key: "dashboard_rag",
    prompt_version: "1",
    prompt_hash: "hash",
    execution_id: "execution-1",
    token_usage: {},
    estimated_cost: "0",
    latency_ms: 42,
    finish_reason: "stop",
    fallback_used: false,
  } });
  vi.mocked(widgetApi.activateWidgetPublicCredential).mockResolvedValue({ success: true, data: { id: "credential-1", public_identifier: "wpk_live_123", status: "active", environment: "production" } });
  vi.mocked(widgetApi.addWidgetOrigin).mockResolvedValue({ success: true, data: { id: "origin-1", origin: "https://example.com", scheme: "https", hostname: "example.com", port: null, wildcard_subdomains: false, environment: "production", active: true, created_at: "2026-08-02T00:00:00.000Z", updated_at: "2026-08-02T00:00:00.000Z" } });
  vi.mocked(widgetApi.validateWidgetPublish).mockResolvedValue({ success: true, data: { publishable: true, errors: [], warnings: [], diff: { changed_fields: ["bot_name"], has_published_revision: false }, knowledge: [] } });
  vi.mocked(widgetApi.publishWidget).mockResolvedValue({ success: true, data: { widget: { ...widget, publication_status: "published", active_published_revision_id: "published-1", active_revision_number: 2 }, published_revision: { ...draft, id: "published-1", status: "published" }, validation_errors: [] } });
  vi.mocked(widgetApi.getWidgetEmbed).mockResolvedValue({ success: true, data: embed });
  vi.mocked(authApi.completeOnboarding).mockResolvedValue({ success: true, data: {} as never });
});

describe("assistant onboarding wizard", () => {
  it("creates the assistant draft from details and inferred company branding", async () => {
    const user = userEvent.setup();
    render(<AssistantOnboardingWizard session={session} />);

    await user.click(screen.getByRole("button", { name: /create your first ai assistant/i }));
    await user.clear(screen.getByLabelText("Assistant name"));
    await user.type(screen.getByLabelText("Assistant name"), "Support Assistant");
    await user.clear(screen.getByLabelText("Assistant description"));
    await user.type(screen.getByLabelText("Assistant description"), "Answers from approved support knowledge.");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(widgetApi.createWidget).toHaveBeenCalledWith(session, expect.objectContaining({ display_name: "Support Assistant", environment: "production" })));
    expect(screen.getByRole("heading", { name: /connect the assistant/i })).toBeTruthy();
  }, 10000);

  it("uploads, trains, indexes selected knowledge, tests chat, publishes, and completes onboarding", async () => {
    const user = userEvent.setup();
    render(<AssistantOnboardingWizard session={session} />);

    await advanceToKnowledge(user);
    const file = new File(["Approved answers"], "handbook.txt", { type: "text/plain" });
    await user.upload(screen.getByLabelText("Upload knowledge files"), file);
    expect(screen.getByText("handbook.txt")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Start training" }));

    await waitFor(() => expect(widgetApi.updateWidgetKnowledgeScope).toHaveBeenCalledWith(session, "widget-1", { document_ids: ["doc-1"], expected_concurrency_version: 1 }));
    expect(await screen.findByText("Training complete. Your assistant is ready to test.")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Ask assistant" }));
    expect(await screen.findByText("The assistant can answer from the uploaded handbook.")).toBeTruthy();
    expect(screen.getByText("High confidence")).toBeTruthy();
    expect(screen.getByText("42 ms")).toBeTruthy();
    expect(screen.getByText("[1] handbook.txt")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Publish assistant" }));
    await waitFor(() => expect(widgetApi.publishWidget).toHaveBeenCalledWith(session, "widget-1", { draft_revision_id: "draft-1", expected_concurrency_version: 2 }));
    expect(await screen.findByText("Published successfully")).toBeTruthy();
    expect(screen.getByText(/data-widget-key/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Finish onboarding" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
  });

  it("surfaces publish validation errors without completing onboarding", async () => {
    vi.mocked(widgetApi.validateWidgetPublish).mockResolvedValue({ success: true, data: { publishable: false, errors: [{ field: "allowed_origins", code: "required", message: "At least one allowed origin is required before publishing." }], warnings: [], diff: {}, knowledge: [] } });
    const user = userEvent.setup();
    render(<AssistantOnboardingWizard session={session} />);

    await advanceToKnowledge(user);
    await user.upload(screen.getByLabelText("Upload knowledge files"), new File(["Approved answers"], "handbook.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Start training" }));
    await screen.findByText("Training complete. Your assistant is ready to test.");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Publish assistant" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("At least one allowed origin is required before publishing.");
    expect(authApi.completeOnboarding).not.toHaveBeenCalled();
  });
});

async function advanceToKnowledge(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /create your first ai assistant/i }));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await waitFor(() => expect(widgetApi.createWidget).toHaveBeenCalled());
  await user.clear(screen.getByLabelText("Website URL"));
  await user.type(screen.getByLabelText("Website URL"), "https://example.com");
  await user.click(screen.getByRole("button", { name: "Continue" }));
}