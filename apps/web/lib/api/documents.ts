import { dashboardApiGet, dashboardApiPost, dashboardApiPostForm } from "./client";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type DocumentRecord = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  title: string;
  source_type: string;
  source_key: string | null;
  status: string;
  category: string | null;
  visibility: string;
  created_by_user_id: string | null;
  active_document_version_id: string | null;
  metadata_json: Record<string, unknown> | null;
  archived_at: string | null;
  expires_at: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentVersionRecord = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  document_id: string;
  version_number: number;
  original_file_path: string | null;
  extracted_text_path: string | null;
  checksum: string;
  processing_status: string;
  processing_error: string | null;
  effective_from: string | null;
  expires_at: string | null;
  created_by_user_id: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type ChunkRecord = {
  id: string;
  organisation_id: string;
  workspace_id: string;
  document_id: string;
  document_version_id: string;
  chunk_index: number;
  content: string;
  content_hash: string;
  token_count: number | null;
  source_type: string;
  source_title: string;
  language: string | null;
  chunking_strategy_version: string | null;
  heading_path: string | null;
  section_title: string | null;
  page_number: number | null;
  parser_name: string | null;
  parser_version: string | null;
  status: string;
  metadata_json: Record<string, unknown> | null;
  embedding_model: string | null;
  embedding_provider: string | null;
  embedding_dimension: number | null;
  embedding_created_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentUploadResult = {
  document: DocumentRecord;
  document_version: DocumentVersionRecord;
};

export type ProcessingMeta = {
  success?: boolean;
  previous_status?: string;
  new_status?: string;
  extracted_text_path?: string | null;
  chunk_count?: number;
  embedded_chunk_count?: number;
  error_code?: string | null;
  error_message?: string | null;
};

export type UploadDocumentInput = {
  file: File;
  title?: string;
  category?: string;
  visibility?: string;
};

function workspacePath(session: DevelopmentDashboardSession, suffix: string) {
  return `/api/v1/workspaces/${session.workspaceId}${suffix}`;
}

function tenantParams(session: DevelopmentDashboardSession) {
  return { organisation_id: session.organisationId };
}

export function listDocuments(session: DevelopmentDashboardSession) {
  return dashboardApiGet<DocumentRecord[]>({
    path: workspacePath(session, "/documents"),
    session,
    searchParams: tenantParams(session),
  });
}

export function getDocument(session: DevelopmentDashboardSession, documentId: string) {
  return dashboardApiGet<DocumentRecord>({
    path: workspacePath(session, `/documents/${documentId}`),
    session,
    searchParams: tenantParams(session),
  });
}

export function uploadDocument(session: DevelopmentDashboardSession, input: UploadDocumentInput) {
  const formData = new FormData();
  formData.set("file", input.file);
  if (input.title?.trim()) formData.set("title", input.title.trim());
  if (input.category?.trim()) formData.set("category", input.category.trim());
  formData.set("visibility", input.visibility || "workspace");

  return dashboardApiPostForm<DocumentUploadResult>({
    path: workspacePath(session, "/documents/upload"),
    session,
    searchParams: tenantParams(session),
    formData,
  });
}

export function listDocumentVersions(session: DevelopmentDashboardSession, documentId: string) {
  return dashboardApiGet<DocumentVersionRecord[]>({
    path: workspacePath(session, `/documents/${documentId}/versions`),
    session,
    searchParams: tenantParams(session),
  });
}

export function getDocumentVersion(session: DevelopmentDashboardSession, documentId: string, versionId: string) {
  return dashboardApiGet<DocumentVersionRecord>({
    path: workspacePath(session, `/documents/${documentId}/versions/${versionId}`),
    session,
    searchParams: tenantParams(session),
  });
}

export function listDocumentChunks(session: DevelopmentDashboardSession, documentId: string, versionId: string) {
  return dashboardApiGet<ChunkRecord[]>({
    path: workspacePath(session, `/documents/${documentId}/versions/${versionId}/chunks`),
    session,
    searchParams: tenantParams(session),
  });
}

export function extractDocumentVersion(session: DevelopmentDashboardSession, documentId: string, versionId: string) {
  return dashboardApiPost<DocumentVersionRecord, ProcessingMeta>({
    path: workspacePath(session, `/documents/${documentId}/versions/${versionId}/extract`),
    session,
    searchParams: tenantParams(session),
  });
}

export function chunkDocumentVersion(session: DevelopmentDashboardSession, documentId: string, versionId: string) {
  return dashboardApiPost<DocumentVersionRecord, ProcessingMeta>({
    path: workspacePath(session, `/documents/${documentId}/versions/${versionId}/chunk`),
    session,
    searchParams: tenantParams(session),
  });
}

export function embedDocumentVersion(session: DevelopmentDashboardSession, documentId: string, versionId: string) {
  return dashboardApiPost<DocumentVersionRecord, ProcessingMeta>({
    path: workspacePath(session, `/documents/${documentId}/versions/${versionId}/embed`),
    session,
    searchParams: tenantParams(session),
  });
}

export function transitionDocument(session: DevelopmentDashboardSession, documentId: string, targetStatus: string) {
  return dashboardApiPost<DocumentRecord, ProcessingMeta>({
    path: workspacePath(session, `/documents/${documentId}/transition`),
    session,
    searchParams: tenantParams(session),
    body: { target_status: targetStatus },
  });
}
