import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { KnowledgeBaseClient } from "./knowledge-base-client";
import type { DocumentRecord, DocumentVersionRecord, ChunkRecord } from "../../lib/api/documents";
import * as documentApi from "../../lib/api/documents";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

vi.mock("../../lib/api/documents");

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

const documentRecord: DocumentRecord = {
  id: "doc-1",
  organisation_id: "org-1",
  workspace_id: "workspace-1",
  title: "Admissions Handbook",
  source_type: "pdf",
  source_key: "admissions.pdf",
  status: "ready",
  category: "policy",
  visibility: "workspace",
  created_by_user_id: "user-1",
  active_document_version_id: "ver-1",
  metadata_json: { file_size_bytes: 2048, original_filename: "admissions.pdf" },
  archived_at: null,
  expires_at: null,
  deleted_at: null,
  created_at: "2026-07-20T00:00:00.000Z",
  updated_at: "2026-07-21T00:00:00.000Z",
};

const versionRecord: DocumentVersionRecord = {
  id: "ver-1",
  organisation_id: "org-1",
  workspace_id: "workspace-1",
  document_id: "doc-1",
  version_number: 1,
  original_file_path: "org/workspace/admissions.pdf",
  extracted_text_path: "org/workspace/extracted.txt",
  checksum: "sha256:abc",
  processing_status: "ready",
  processing_error: null,
  effective_from: null,
  expires_at: null,
  created_by_user_id: "user-1",
  metadata_json: { file_size_bytes: 2048, extraction: { parser: "txt" } },
  created_at: "2026-07-20T00:00:00.000Z",
  updated_at: "2026-07-21T00:00:00.000Z",
};

const chunkRecord: ChunkRecord = {
  id: "chunk-1",
  organisation_id: "org-1",
  workspace_id: "workspace-1",
  document_id: "doc-1",
  document_version_id: "ver-1",
  chunk_index: 0,
  content: "Applications close in December.",
  content_hash: "sha256:chunk",
  token_count: 5,
  source_type: "pdf",
  source_title: "Admissions Handbook",
  language: "en",
  chunking_strategy_version: "mvp-word-v1",
  heading_path: null,
  section_title: null,
  page_number: 1,
  parser_name: null,
  parser_version: null,
  status: "ready",
  metadata_json: null,
  embedding_model: "local-mock-v1",
  embedding_provider: "local-mock",
  embedding_dimension: 8,
  embedding_created_at: "2026-07-21T01:00:00.000Z",
  created_at: "2026-07-21T00:00:00.000Z",
  updated_at: "2026-07-21T01:00:00.000Z",
};

function envelope<T>(data: T) {
  return { success: true, data, meta: {} };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(documentApi.listDocuments).mockResolvedValue(envelope([documentRecord]));
  vi.mocked(documentApi.listDocumentVersions).mockResolvedValue(envelope([versionRecord]));
  vi.mocked(documentApi.listDocumentChunks).mockResolvedValue(envelope([chunkRecord]));
  vi.mocked(documentApi.uploadDocument).mockResolvedValue(envelope({ document: documentRecord, document_version: versionRecord }));
  vi.mocked(documentApi.extractDocumentVersion).mockResolvedValue(envelope(versionRecord));
  vi.mocked(documentApi.chunkDocumentVersion).mockResolvedValue(envelope(versionRecord));
  vi.mocked(documentApi.embedDocumentVersion).mockResolvedValue(envelope(versionRecord));
  vi.mocked(documentApi.transitionDocument).mockResolvedValue(envelope({ ...documentRecord, status: "archived" }));
});

describe("KnowledgeBaseClient", () => {
  it("renders summary, document rows, and unsupported action guidance", () => {
    render(<KnowledgeBaseClient session={session} initialDocuments={[documentRecord]} />);

    expect(screen.getByRole("heading", { name: /operational source control/i })).toBeInTheDocument();
    expect(screen.getAllByText("Admissions Handbook").length).toBeGreaterThan(0);
    expect(screen.getByText("policy")).toBeInTheDocument();
    expect(screen.getByText("Raw extracted text download is not exposed by the current API; metadata and extraction path are shown instead.")).toBeInTheDocument();
  });

  it("renders the empty state", () => {
    render(<KnowledgeBaseClient session={session} initialDocuments={[]} />);

    expect(screen.getByRole("heading", { name: "No documents yet" })).toBeInTheDocument();
  });

  it("loads versions and chunks for document details", async () => {
    const user = userEvent.setup();
    render(<KnowledgeBaseClient session={session} initialDocuments={[documentRecord]} />);

    await user.click(screen.getByRole("button", { name: /view details for admissions handbook/i }));

    expect(documentApi.listDocumentVersions).toHaveBeenCalledWith(session, "doc-1");
    expect(documentApi.listDocumentChunks).toHaveBeenCalledWith(session, "doc-1", "ver-1");
    expect(await screen.findByText("Applications close in December.")).toBeInTheDocument();
  });

  it("uploads a document and refreshes the list", async () => {
    const user = userEvent.setup();
    render(<KnowledgeBaseClient session={session} initialDocuments={[]} />);

    const uploadInput = screen.getByLabelText("Document file") as HTMLInputElement;
    const file = new File(["content"], "policy.txt", { type: "text/plain" });
    Object.defineProperty(uploadInput, "files", { value: [file], configurable: true });
    fireEvent.change(uploadInput);
    await user.type(screen.getByLabelText("Display name"), "Admissions Policy");
    await user.click(screen.getByRole("button", { name: "Upload document" }));

    await waitFor(() => expect(documentApi.uploadDocument).toHaveBeenCalled());
    expect(documentApi.listDocuments).toHaveBeenCalledWith(session);
    expect(await screen.findByText("Admissions Handbook uploaded.")).toBeInTheDocument();
  });

  it("runs supported extraction when the active version is uploaded", async () => {
    const user = userEvent.setup();
    vi.mocked(documentApi.listDocumentVersions).mockResolvedValue(envelope([{ ...versionRecord, processing_status: "uploaded", extracted_text_path: null }]));
    vi.mocked(documentApi.listDocumentChunks).mockResolvedValue(envelope([]));
    render(<KnowledgeBaseClient session={session} initialDocuments={[{ ...documentRecord, status: "uploaded" }]} />);

    await user.click(screen.getByRole("button", { name: /view details/i }));
    await user.click(await screen.findByRole("button", { name: "Extract" }));

    await waitFor(() => expect(documentApi.extractDocumentVersion).toHaveBeenCalledWith(session, "doc-1", "ver-1"));
  });

  it("confirms archive before using the lifecycle transition", async () => {
    const user = userEvent.setup();
    render(<KnowledgeBaseClient session={session} initialDocuments={[documentRecord]} />);

    await user.click(screen.getByRole("button", { name: "Archive" }));
    const dialog = screen.getByRole("dialog", { name: "Archive document?" });
    expect(dialog).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Archive" }));

    await waitFor(() => expect(documentApi.transitionDocument).toHaveBeenCalledWith(session, "doc-1", "archived"));
  });

  it("shows API errors", async () => {
    const user = userEvent.setup();
    vi.mocked(documentApi.listDocumentVersions).mockRejectedValue(new Error("network down"));
    render(<KnowledgeBaseClient session={session} initialDocuments={[documentRecord]} />);

    await user.click(screen.getByRole("button", { name: /view details/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Document details could not be loaded.");
  });
});
