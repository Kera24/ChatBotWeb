"use client";

import { useMemo, useState, type FormEvent } from "react";

import { messageForApiError, isDashboardApiError } from "../../lib/api/errors";
import {
  chunkDocumentVersion,
  embedDocumentVersion,
  extractDocumentVersion,
  listDocumentChunks,
  listDocumentVersions,
  listDocuments,
  transitionDocument,
  uploadDocument,
  type ChunkRecord,
  type DocumentRecord,
  type DocumentVersionRecord,
} from "../../lib/api/documents";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type KnowledgeBaseClientProps = {
  session: DevelopmentDashboardSession;
  initialDocuments: DocumentRecord[];
};

type DetailState = {
  versions: DocumentVersionRecord[];
  chunks: ChunkRecord[];
};

type ConfirmState = {
  documentId: string;
  title: string;
  targetStatus: "archived";
} | null;

const PROCESSING_STATUSES = new Set(["uploaded", "pending", "queued", "processing", "extracting", "chunking", "embedding"]);
const READY_STATUSES = new Set(["ready", "completed"]);

export function KnowledgeBaseClient({ session, initialDocuments }: KnowledgeBaseClientProps) {
  const [documents, setDocuments] = useState(initialDocuments);
  const [selectedDocumentId, setSelectedDocumentId] = useState(initialDocuments[0]?.id ?? "");
  const [details, setDetails] = useState<Record<string, DetailState>>({});
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({});
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const selectedDocument = documents.find((document) => document.id === selectedDocumentId) ?? documents[0] ?? null;
  const selectedDetails = selectedDocument ? details[selectedDocument.id] : undefined;
  const activeVersion = selectedDocument ? activeVersionFor(selectedDocument, selectedDetails?.versions ?? []) : null;
  const summary = useMemo(() => buildSummary(documents, details), [documents, details]);

  async function refreshDocuments(nextSelectedId = selectedDocumentId) {
    const response = await listDocuments(session);
    setDocuments(response.data);
    if (response.data.length === 0) {
      setSelectedDocumentId("");
    } else if (nextSelectedId && response.data.some((document) => document.id === nextSelectedId)) {
      setSelectedDocumentId(nextSelectedId);
    } else {
      setSelectedDocumentId(response.data[0].id);
    }
  }

  async function loadDetails(document: DocumentRecord) {
    setError(null);
    setLoadingDetails((current) => ({ ...current, [document.id]: true }));
    try {
      const versions = await listDocumentVersions(session, document.id);
      const active = activeVersionFor(document, versions.data);
      const chunks = active ? await listDocumentChunks(session, document.id, active.id) : null;
      setDetails((current) => ({
        ...current,
        [document.id]: { versions: versions.data, chunks: chunks?.data ?? [] },
      }));
    } catch (caught) {
      setError(errorMessage(caught, "Document details could not be loaded."));
    } finally {
      setLoadingDetails((current) => ({ ...current, [document.id]: false }));
    }
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const form = event.currentTarget;
    const formData = new FormData(form);
    const fileInput = form.elements.namedItem("file") as HTMLInputElement | null;
    const file = uploadFile ?? fileInput?.files?.[0] ?? null;
    if (!file || file.size === 0) {
      setError("Choose a document before uploading.");
      return;
    }

    setUploading(true);
    try {
      const result = await uploadDocument(session, {
        file,
        title: String(formData.get("title") ?? ""),
        category: String(formData.get("category") ?? ""),
        visibility: "workspace",
      });
      form.reset();
      setUploadFile(null);
      setNotice(`${result.data.document.title} uploaded.`);
      await refreshDocuments(result.data.document.id);
      setDetails((current) => ({
        ...current,
        [result.data.document.id]: { versions: [result.data.document_version], chunks: [] },
      }));
    } catch (caught) {
      setError(errorMessage(caught, "Document upload failed."));
    } finally {
      setUploading(false);
    }
  }

  async function runVersionAction(action: "extract" | "chunk" | "embed") {
    if (!selectedDocument || !activeVersion) return;
    setError(null);
    setNotice(null);
    setBusyAction(action);
    try {
      if (action === "extract") await extractDocumentVersion(session, selectedDocument.id, activeVersion.id);
      if (action === "chunk") await chunkDocumentVersion(session, selectedDocument.id, activeVersion.id);
      if (action === "embed") await embedDocumentVersion(session, selectedDocument.id, activeVersion.id);
      await loadDetails(selectedDocument);
      await refreshDocuments(selectedDocument.id);
      setNotice(`${actionLabel(action)} completed for ${selectedDocument.title}.`);
    } catch (caught) {
      setError(errorMessage(caught, `${actionLabel(action)} could not be completed.`));
    } finally {
      setBusyAction(null);
    }
  }

  async function runConfirmedTransition() {
    if (!confirm) return;
    setBusyAction("archive");
    setError(null);
    setNotice(null);
    try {
      await transitionDocument(session, confirm.documentId, confirm.targetStatus);
      await refreshDocuments(confirm.documentId);
      setNotice(`${confirm.title} archived.`);
      setConfirm(null);
    } catch (caught) {
      setError(errorMessage(caught, "Document could not be archived."));
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <section className="knowledgeBasePage" aria-labelledby="knowledge-title">
      <div className="knowledgeHero">
        <div>
          <p className="eyebrow">Yuranix Knowledge Base</p>
          <h2 id="knowledge-title">Operational source control for grounded answers</h2>
          <p>Upload, inspect, process, and retire workspace-scoped sources through the existing document lifecycle.</p>
        </div>
        <div className="knowledgeHeroAside">
          <strong>{summary.ready}</strong>
          <span>ready or indexed sources</span>
        </div>
      </div>

      <div className="knowledgeSummary" aria-label="Knowledge base summary">
        <Metric label="Total documents" value={summary.total} />
        <Metric label="Processing" value={summary.processing} />
        <Metric label="Failed" value={summary.failed} />
        <Metric label="Known chunks" value={summary.chunks} />
        <Metric label="Most recent update" value={summary.updatedAt ? formatDate(summary.updatedAt) : "No activity"} compact />
      </div>

      {notice ? <div className="widgetNotice" role="status">{notice}</div> : null}
      {error ? <div className="statePanel urgentState" role="alert"><h2>Knowledge action failed</h2><p>{error}</p></div> : null}

      <div className="knowledgeGrid">
        <section className="knowledgePanel" aria-labelledby="upload-title">
          <div className="panelHeaderLine">
            <div>
              <p className="sectionKicker">Upload</p>
              <h3 id="upload-title">Add a source</h3>
            </div>
            <span className="knowledgePill">Workspace only</span>
          </div>
          <form className="knowledgeUploadForm" onSubmit={handleUpload}>
            <label>
              Document file
              <input name="file" type="file" aria-describedby="upload-help" onChange={(event) => setUploadFile(event.currentTarget.files?.[0] ?? null)} />
            </label>
            <label>
              Display name
              <input name="title" type="text" placeholder="Admissions policy" />
            </label>
            <label>
              Category
              <input name="category" type="text" placeholder="Policy, handbook, FAQ" />
            </label>
            <p id="upload-help" className="mutedText">Supported file types and size limits are enforced by the backend upload service.</p>
            <button className="actionButton knowledgePrimaryButton" type="submit" disabled={uploading}>{uploading ? "Uploading" : "Upload document"}</button>
          </form>
        </section>

        <section className="knowledgePanel" aria-labelledby="unsupported-title">
          <p className="sectionKicker">Contracts</p>
          <h3 id="unsupported-title">Available actions</h3>
          <ul className="knowledgeCapabilityList">
            <li>Raw extracted text download is not exposed by the current API; metadata and extraction path are shown instead.</li>
            <li>Hard delete is not exposed. Ready documents can be archived through the lifecycle endpoint.</li>
            <li>Failed versions are terminal in the current lifecycle and do not expose retry from failed state.</li>
          </ul>
        </section>
      </div>

      <section className="knowledgePanel" aria-labelledby="document-table-title">
        <div className="panelHeaderLine">
          <div>
            <p className="sectionKicker">Sources</p>
            <h3 id="document-table-title">Documents</h3>
          </div>
          <button className="smallButton" type="button" onClick={() => void refreshDocuments()} aria-label="Refresh documents">Refresh</button>
        </div>

        {documents.length === 0 ? (
          <div className="knowledgeEmptyState">
            <h3>No documents yet</h3>
            <p>Upload the first source to make workspace knowledge available for extraction, chunking, and embedding.</p>
          </div>
        ) : (
          <div className="knowledgeTableWrap">
            <table className="knowledgeTable">
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Source</th>
                  <th scope="col">Lifecycle</th>
                  <th scope="col">Version</th>
                  <th scope="col">Size</th>
                  <th scope="col">Uploaded</th>
                  <th scope="col">Indexed</th>
                  <th scope="col">Chunks</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((document) => {
                  const detail = details[document.id];
                  const version = activeVersionFor(document, detail?.versions ?? []);
                  const chunks = detail?.chunks ?? [];
                  const selected = selectedDocument?.id === document.id;
                  return (
                    <tr key={document.id} className={selected ? "knowledgeSelectedRow" : undefined}>
                      <td><strong>{document.title}</strong><span>{document.category || "Uncategorised"}</span></td>
                      <td>{document.source_type}</td>
                      <td><StatusBadge status={document.status} /></td>
                      <td>{version ? `v${version.version_number}` : "None"}</td>
                      <td>{formatBytes(numberMetadata(version?.metadata_json, "file_size_bytes") ?? numberMetadata(document.metadata_json, "file_size_bytes"))}</td>
                      <td>{formatDate(document.created_at)}</td>
                      <td>{latestIndexedAt(chunks) ? formatDate(latestIndexedAt(chunks) as string) : "Not indexed"}</td>
                      <td>{chunks.length || "-"}</td>
                      <td>
                        <button
                          className="smallButton"
                          type="button"
                          onClick={() => { setSelectedDocumentId(document.id); void loadDetails(document); }}
                          aria-label={`View details for ${document.title}`}
                        >
                          {loadingDetails[document.id] ? "Loading" : "Details"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selectedDocument ? (
        <DocumentDetailPanel
          document={selectedDocument}
          details={selectedDetails}
          activeVersion={activeVersion}
          loading={Boolean(loadingDetails[selectedDocument.id])}
          busyAction={busyAction}
          onLoad={() => void loadDetails(selectedDocument)}
          onExtract={() => void runVersionAction("extract")}
          onChunk={() => void runVersionAction("chunk")}
          onEmbed={() => void runVersionAction("embed")}
          onArchive={() => setConfirm({ documentId: selectedDocument.id, title: selectedDocument.title, targetStatus: "archived" })}
        />
      ) : null}

      {confirm ? (
        <div className="dialogBackdrop" role="presentation">
          <div className="confirmDialog" role="dialog" aria-modal="true" aria-labelledby="archive-title">
            <h2 id="archive-title">Archive document?</h2>
            <p className="mutedText">{confirm.title} will be removed from active knowledge selection. This uses the backend lifecycle transition and cannot be undone through the current dashboard.</p>
            <div className="formActions">
              <button className="actionButton dangerAction" type="button" onClick={() => void runConfirmedTransition()} disabled={busyAction === "archive"}>{busyAction === "archive" ? "Archiving" : "Archive"}</button>
              <button className="smallButton" type="button" onClick={() => setConfirm(null)}>Cancel</button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function DocumentDetailPanel({
  document,
  details,
  activeVersion,
  loading,
  busyAction,
  onLoad,
  onExtract,
  onChunk,
  onEmbed,
  onArchive,
}: {
  document: DocumentRecord;
  details: DetailState | undefined;
  activeVersion: DocumentVersionRecord | null;
  loading: boolean;
  busyAction: string | null;
  onLoad: () => void;
  onExtract: () => void;
  onChunk: () => void;
  onEmbed: () => void;
  onArchive: () => void;
}) {
  const chunks = details?.chunks ?? [];
  const canExtract = activeVersion?.processing_status === "uploaded";
  const canChunk = activeVersion?.processing_status === "ready" && Boolean(activeVersion.extracted_text_path) && chunks.length === 0;
  const canEmbed = activeVersion?.processing_status === "ready" && chunks.length > 0 && chunks.some((chunk) => !chunk.embedding_created_at);
  const canArchive = document.status === "ready";

  return (
    <section className="knowledgePanel knowledgeDetailPanel" aria-labelledby="detail-title">
      <div className="panelHeaderLine">
        <div>
          <p className="sectionKicker">Selected source</p>
          <h3 id="detail-title">{document.title}</h3>
        </div>
        <button className="smallButton" type="button" onClick={onLoad}>{loading ? "Loading" : "Load details"}</button>
      </div>

      <dl className="knowledgeFacts">
        <div><dt>Document ID</dt><dd>{document.id}</dd></div>
        <div><dt>Source key</dt><dd>{document.source_key || "None"}</dd></div>
        <div><dt>Visibility</dt><dd>{document.visibility}</dd></div>
        <div><dt>Updated</dt><dd>{formatDate(document.updated_at)}</dd></div>
      </dl>

      <div className="knowledgeActionBar" aria-label="Supported document actions">
        <button className="actionButton knowledgePrimaryButton" type="button" onClick={onExtract} disabled={!canExtract || busyAction === "extract"}>{busyAction === "extract" ? "Extracting" : "Extract"}</button>
        <button className="actionButton" type="button" onClick={onChunk} disabled={!canChunk || busyAction === "chunk"}>{busyAction === "chunk" ? "Chunking" : "Chunk"}</button>
        <button className="actionButton" type="button" onClick={onEmbed} disabled={!canEmbed || busyAction === "embed"}>{busyAction === "embed" ? "Indexing" : "Embed"}</button>
        <button className="actionButton dangerAction" type="button" onClick={onArchive} disabled={!canArchive}>Archive</button>
      </div>

      {activeVersion ? (
        <div className="knowledgeDetailGrid">
          <section>
            <h4>Versions</h4>
            <div className="knowledgeVersionList" role="list">
              {(details?.versions ?? [activeVersion]).map((version) => (
                <article className="knowledgeVersionItem" role="listitem" key={version.id}>
                  <strong>Version {version.version_number}</strong>
                  <StatusBadge status={version.processing_status} />
                  {version.processing_error ? <p className="errorText">{version.processing_error}</p> : null}
                  <dl className="knowledgeFacts compactFacts">
                    <div><dt>Checksum</dt><dd>{version.checksum}</dd></div>
                    <div><dt>Original file</dt><dd>{version.original_file_path || "Not stored"}</dd></div>
                    <div><dt>Extracted text</dt><dd>{version.extracted_text_path || "Not extracted"}</dd></div>
                    <div><dt>Metadata</dt><dd>{metadataSummary(version.metadata_json)}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          </section>

          <section>
            <h4>Chunks</h4>
            {chunks.length === 0 ? <p className="mutedText">No chunks are available for the active version.</p> : null}
            <div className="knowledgeChunkList" role="list">
              {chunks.map((chunk) => (
                <article className="knowledgeChunkItem" role="listitem" key={chunk.id}>
                  <strong>Chunk {chunk.chunk_index + 1}</strong>
                  <p>{chunk.content}</p>
                  <dl className="knowledgeFacts compactFacts">
                    <div><dt>Tokens</dt><dd>{chunk.token_count ?? "Unknown"}</dd></div>
                    <div><dt>Embedding</dt><dd>{chunk.embedding_created_at ? `${chunk.embedding_provider || "provider"} at ${formatDate(chunk.embedding_created_at)}` : "Not embedded"}</dd></div>
                    <div><dt>Status</dt><dd>{chunk.status}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          </section>
        </div>
      ) : (
        <p className="mutedText">Load details to inspect versions, metadata, and chunks.</p>
      )}
    </section>
  );
}

function Metric({ label, value, compact = false }: { label: string; value: string | number; compact?: boolean }) {
  return <div className={compact ? "knowledgeMetric compactMetric" : "knowledgeMetric"}><strong>{value}</strong><span>{label}</span></div>;
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`statusBadge status-${status}`}><span className="statusBadgeDot" aria-hidden="true" />{status.replaceAll("_", " ")}</span>;
}

function activeVersionFor(document: DocumentRecord, versions: DocumentVersionRecord[]) {
  return versions.find((version) => version.id === document.active_document_version_id) ?? versions[0] ?? null;
}

function buildSummary(documents: DocumentRecord[], details: Record<string, DetailState>) {
  const total = documents.length;
  const ready = documents.filter((document) => READY_STATUSES.has(document.status) || READY_STATUSES.has(activeVersionFor(document, details[document.id]?.versions ?? [])?.processing_status ?? "")).length;
  const processing = documents.filter((document) => PROCESSING_STATUSES.has(document.status) || PROCESSING_STATUSES.has(activeVersionFor(document, details[document.id]?.versions ?? [])?.processing_status ?? "")).length;
  const failed = documents.filter((document) => document.status === "failed" || activeVersionFor(document, details[document.id]?.versions ?? [])?.processing_status === "failed").length;
  const chunks = Object.values(details).reduce((totalChunks, detail) => totalChunks + detail.chunks.length, 0);
  const updatedAt = documents.map((document) => document.updated_at).sort().at(-1) ?? null;
  return { total, ready, processing, failed, chunks, updatedAt };
}

function latestIndexedAt(chunks: ChunkRecord[]) {
  return chunks.map((chunk) => chunk.embedding_created_at).filter(Boolean).sort().at(-1) ?? null;
}

function numberMetadata(metadata: Record<string, unknown> | null | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === "number" ? value : null;
}

function formatBytes(value: number | null) {
  if (value === null) return "Unknown";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function metadataSummary(metadata: Record<string, unknown> | null) {
  if (!metadata || Object.keys(metadata).length === 0) return "None";
  return Object.keys(metadata).join(", ");
}

function actionLabel(action: "extract" | "chunk" | "embed") {
  if (action === "embed") return "Indexing";
  return action[0].toUpperCase() + action.slice(1);
}

function errorMessage(caught: unknown, fallback: string) {
  if (isDashboardApiError(caught)) return messageForApiError(caught);
  return fallback;
}
