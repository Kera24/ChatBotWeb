"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Archive, CheckCircle2, ChevronDown, Clock3, Database, ExternalLink, FileText, Filter, FolderOpen, Info, Layers3, ListFilter, Loader2, MoreHorizontal, RefreshCw, Search, ShieldCheck, Sparkles, UploadCloud, XCircle } from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent, type KeyboardEvent, type MutableRefObject } from "react";

import { messageForApiError, isDashboardApiError } from "../../lib/api/errors";
import { chunkDocumentVersion, embedDocumentVersion, extractDocumentVersion, listDocumentChunks, listDocumentVersions, listDocuments, transitionDocument, uploadDocument, type ChunkRecord, type DocumentRecord, type DocumentVersionRecord } from "../../lib/api/documents";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type KnowledgeBaseClientProps = { session: DevelopmentDashboardSession; assistantId: string; initialDocuments: DocumentRecord[] };
type DetailState = { versions: DocumentVersionRecord[]; chunks: ChunkRecord[] };
type ConfirmState = { documentId: string; title: string; targetStatus: "archived" } | null;
type ViewMode = "table" | "cards";
type StatusFilter = "all" | "ready" | "processing" | "failed" | "archived";
type SortKey = "updated" | "name" | "status";

const PROCESSING_STATUSES = new Set(["uploaded", "pending", "queued", "processing", "extracting", "chunking", "embedding"]);
const READY_STATUSES = new Set(["ready", "completed", "indexed"]);
const FAILED_STATUSES = new Set(["failed", "error"]);
const ACCEPTED_FORMATS = ".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const TIMELINE_STAGES = ["Uploaded", "Extracting", "Extracted", "Chunking", "Chunked", "Embedding", "Indexed/Ready"];

export function KnowledgeBaseClient({ session, assistantId, initialDocuments }: KnowledgeBaseClientProps) {
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
  const [dragActive, setDragActive] = useState(false);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("updated");
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [menuDocumentId, setMenuDocumentId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const reduceMotion = useReducedMotion();

  const selectedDocument = documents.find((document) => document.id === selectedDocumentId) ?? documents[0] ?? null;
  const selectedDetails = selectedDocument ? details[selectedDocument.id] : undefined;
  const activeVersion = selectedDocument ? activeVersionFor(selectedDocument, selectedDetails?.versions ?? []) : null;
  const summary = useMemo(() => buildSummary(documents, details), [documents, details]);
  const filteredDocuments = useMemo(() => filterAndSortDocuments(documents, details, query, statusFilter, sortKey), [documents, details, query, statusFilter, sortKey]);

  async function refreshDocuments(nextSelectedId = selectedDocumentId) {
    const response = await listDocuments(session, assistantId);
    setDocuments(response.data);
    if (response.data.length === 0) setSelectedDocumentId("");
    else if (nextSelectedId && response.data.some((document) => document.id === nextSelectedId)) setSelectedDocumentId(nextSelectedId);
    else setSelectedDocumentId(response.data[0].id);
  }

  async function loadDetails(document: DocumentRecord) {
    setError(null);
    setLoadingDetails((current) => ({ ...current, [document.id]: true }));
    try {
      const versions = await listDocumentVersions(session, document.id);
      const active = activeVersionFor(document, versions.data);
      const chunks = active ? await listDocumentChunks(session, document.id, active.id) : null;
      setDetails((current) => ({ ...current, [document.id]: { versions: versions.data, chunks: chunks?.data ?? [] } }));
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
      const result = await uploadDocument(session, { file, title: String(formData.get("title") ?? ""), category: String(formData.get("category") ?? ""), visibility: "workspace", assistantId });
      form.reset();
      setUploadFile(null);
      setNotice(`${result.data.document.title} uploaded.`);
      await refreshDocuments(result.data.document.id);
      setDetails((current) => ({ ...current, [result.data.document.id]: { versions: [result.data.document_version], chunks: [] } }));
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

  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.35 } };

  return (
    <motion.section className="knowledgeBasePage premiumKnowledgePage" aria-labelledby="knowledge-title" {...pageMotion}>
      <header className="knowledgeControlHeader">
        <div className="knowledgeHeaderCopy">
          <p className="knowledgeEyebrow"><Database size={14} aria-hidden="true" />Conversa Knowledge Base</p>
          <h2 id="knowledge-title">Knowledge Base</h2>
          <p>Manage trusted sources for the selected assistant. Uploads, processing, and retrieval scope stay tied to this assistant context.</p>
          <div className="knowledgeContextLine" aria-label="Assistant knowledge context"><span><ShieldCheck size={14} aria-hidden="true" />Assistant scoped</span><span>Current assistant: <strong>{assistantId}</strong></span></div>
        </div>
        <div className="knowledgeHeaderActions"><button className="knowledgeButton secondary" type="button" onClick={() => void refreshDocuments()} aria-label="Refresh assistant knowledge"><RefreshCw size={16} aria-hidden="true" />Refresh</button><button className="knowledgeButton primary" type="button" onClick={() => fileInputRef.current?.click()}><UploadCloud size={16} aria-hidden="true" />Add Knowledge</button></div>
      </header>

      <KnowledgeMetrics summary={summary} />
      <AnimatePresence>{notice ? <motion.div className="knowledgeToast success" role="status" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}><CheckCircle2 size={16} aria-hidden="true" />{notice}</motion.div> : null}{error ? <motion.div className="knowledgeToast danger" role="alert" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}><XCircle size={16} aria-hidden="true" /><span><strong>Knowledge action failed.</strong> {error}</span></motion.div> : null}</AnimatePresence>

      <div className="knowledgeWorkspaceGrid">
        <KnowledgeUpload fileInputRef={fileInputRef} uploadFile={uploadFile} uploading={uploading} dragActive={dragActive} setDragActive={setDragActive} onFileChange={(event) => { setUploadFile(event.currentTarget.files?.[0] ?? null); setNotice(null); setError(null); }} onSelectFile={(file) => { setUploadFile(file); setNotice(null); setError(null); }} onSubmit={handleUpload} />
        <section className="knowledgePanel knowledgeGuidancePanel" aria-labelledby="knowledge-scope-title"><div className="knowledgePanelHeader compact"><div><p>Assistant Scope</p><h3 id="knowledge-scope-title">Supported actions</h3></div><span className="knowledgePill"><Info size={13} aria-hidden="true" />API backed</span></div><ul className="knowledgeCapabilityList"><li><CheckCircle2 size={15} aria-hidden="true" />Uploads are sent with the selected assistant context.</li><li><CheckCircle2 size={15} aria-hidden="true" />Versions, chunks, extraction, embedding, and archive use existing lifecycle endpoints.</li><li><Info size={15} aria-hidden="true" />Raw extracted text download is not exposed by the current API; metadata and extraction path are shown instead.</li><li><Info size={15} aria-hidden="true" />Hard delete and failed-version retry are not exposed in the current dashboard.</li></ul></section>
      </div>

      <section className="knowledgePanel knowledgeDocumentsPanel" aria-labelledby="document-table-title">
        <div className="knowledgePanelHeader documentHeader"><div><p>Assistant Sources</p><h3 id="document-table-title">Documents</h3></div><KnowledgeFilters query={query} setQuery={setQuery} statusFilter={statusFilter} setStatusFilter={setStatusFilter} sortKey={sortKey} setSortKey={setSortKey} viewMode={viewMode} setViewMode={setViewMode} /></div>
        <p className="knowledgeFilterNote"><ListFilter size={14} aria-hidden="true" />Search, filters, and sorting are applied locally to the assistant-scoped results returned by the backend.</p>
        {documents.length === 0 ? <KnowledgeEmptyState onAdd={() => fileInputRef.current?.click()} /> : filteredDocuments.length === 0 ? <div className="knowledgeEmptyState compact"><Search size={28} aria-hidden="true" /><h3>No matching documents</h3><p>Adjust the search, status filter, or sort to return to this assistant&apos;s available sources.</p></div> : viewMode === "cards" ? <div className="knowledgeCardGrid" role="list" aria-label="Assistant documents">{filteredDocuments.map((document, index) => <DocumentCard key={document.id} document={document} detail={details[document.id]} selected={selectedDocument?.id === document.id} loading={Boolean(loadingDetails[document.id])} menuOpen={menuDocumentId === document.id} setMenuOpen={(open) => setMenuDocumentId(open ? document.id : null)} onDetails={() => { setSelectedDocumentId(document.id); void loadDetails(document); }} onArchive={() => setConfirm({ documentId: document.id, title: document.title, targetStatus: "archived" })} index={index} />)}</div> : <DocumentTable documents={filteredDocuments} details={details} selectedDocumentId={selectedDocument?.id ?? ""} loadingDetails={loadingDetails} menuDocumentId={menuDocumentId} setMenuDocumentId={setMenuDocumentId} onDetails={(document) => { setSelectedDocumentId(document.id); void loadDetails(document); }} onArchive={(document) => setConfirm({ documentId: document.id, title: document.title, targetStatus: "archived" })} />}
      </section>

      {selectedDocument ? <DocumentDetailPanel document={selectedDocument} assistantId={assistantId} details={selectedDetails} activeVersion={activeVersion} loading={Boolean(loadingDetails[selectedDocument.id])} busyAction={busyAction} onLoad={() => void loadDetails(selectedDocument)} onExtract={() => void runVersionAction("extract")} onChunk={() => void runVersionAction("chunk")} onEmbed={() => void runVersionAction("embed")} onArchive={() => setConfirm({ documentId: selectedDocument.id, title: selectedDocument.title, targetStatus: "archived" })} /> : null}
      <AnimatePresence>{confirm ? <motion.div className="dialogBackdrop knowledgeDialogBackdrop" role="presentation" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><motion.div className="confirmDialog knowledgeConfirmDialog" role="dialog" aria-modal="true" aria-labelledby="archive-title" initial={{ opacity: 0, y: 18, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 18, scale: 0.98 }}><h2 id="archive-title">Archive document?</h2><p>{confirm.title} will be removed from active knowledge selection. This uses the existing lifecycle transition and cannot be undone through the current dashboard.</p><div className="formActions"><button className="knowledgeButton danger" type="button" onClick={() => void runConfirmedTransition()} disabled={busyAction === "archive"}>{busyAction === "archive" ? <Loader2 className="spinIcon" size={16} aria-hidden="true" /> : <Archive size={16} aria-hidden="true" />}{busyAction === "archive" ? "Archiving" : "Archive"}</button><button className="knowledgeButton secondary" type="button" onClick={() => setConfirm(null)}>Cancel</button></div></motion.div></motion.div> : null}</AnimatePresence>
    </motion.section>
  );
}

function KnowledgeMetrics({ summary }: { summary: ReturnType<typeof buildSummary> }) {
  const metrics = [
    { label: "Total documents", value: summary.total, helper: "Assistant-scoped sources", icon: FileText },
    { label: "Ready / indexed", value: summary.ready, helper: "Available for grounded answers", icon: CheckCircle2 },
    { label: "Processing", value: summary.processing, helper: "Moving through lifecycle", icon: Clock3 },
    { label: "Failed", value: summary.failed, helper: "Needs operator review", icon: XCircle },
    { label: "Known chunks", value: summary.chunks, helper: "Loaded from inspected versions", icon: Layers3 },
    { label: "Last update", value: summary.updatedAt ? formatDate(summary.updatedAt) : "No activity", helper: "Latest document change", icon: Sparkles, wide: true },
  ];
  return <div className="knowledgeMetrics" aria-label="Knowledge summary metrics">{metrics.map((metric, index) => <motion.div className={metric.wide ? "knowledgeMetricCard wide" : "knowledgeMetricCard"} key={metric.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.035 }}><metric.icon size={18} aria-hidden="true" /><strong>{metric.value}</strong><span>{metric.label}</span><small>{metric.helper}</small></motion.div>)}</div>;
}

function KnowledgeUpload({ fileInputRef, uploadFile, uploading, dragActive, setDragActive, onFileChange, onSelectFile, onSubmit }: { fileInputRef: MutableRefObject<HTMLInputElement | null>; uploadFile: File | null; uploading: boolean; dragActive: boolean; setDragActive: (active: boolean) => void; onFileChange: (event: ChangeEvent<HTMLInputElement>) => void; onSelectFile: (file: File | null) => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    onSelectFile(event.dataTransfer.files?.[0] ?? null);
  }
  return <section className="knowledgePanel knowledgeUploadPanel" aria-labelledby="upload-title"><div className="knowledgePanelHeader compact"><div><p>Upload</p><h3 id="upload-title">Add Knowledge</h3></div><span className="knowledgePill"><UploadCloud size={13} aria-hidden="true" />PDF, DOCX, TXT</span></div><form className="knowledgeUploadForm premiumUploadForm" onSubmit={onSubmit}><label className={dragActive ? "knowledgeDropzone active" : "knowledgeDropzone"} onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragActive(false)} onDrop={handleDrop} onKeyDown={(event: KeyboardEvent<HTMLLabelElement>) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); fileInputRef.current?.click(); } }} tabIndex={0}><span className="knowledgeDropIcon"><UploadCloud size={24} aria-hidden="true" /></span><strong>{uploadFile ? uploadFile.name : "Drop a source file here"}</strong><span>{uploadFile ? `${formatBytes(uploadFile.size)} selected` : "Browse or drag a PDF, DOCX, or TXT document."}</span><input ref={fileInputRef} name="file" type="file" aria-label="Document file" aria-describedby="upload-help" accept={ACCEPTED_FORMATS} onChange={onFileChange} /></label><div className="knowledgeUploadFields"><label>Display name<input name="title" type="text" placeholder="Admissions policy" /></label><label>Category<input name="category" type="text" placeholder="Policy, handbook, FAQ" /></label></div><p id="upload-help" className="knowledgeMuted">Supported file types are PDF, DOCX, and TXT. File-size limits are enforced by the backend upload service.</p>{uploading ? <div className="knowledgeUploadProgress" role="status"><span />Uploading source into the assistant knowledge pipeline</div> : null}<button className="knowledgeButton primary" type="submit" disabled={uploading}>{uploading ? <Loader2 className="spinIcon" size={16} aria-hidden="true" /> : <UploadCloud size={16} aria-hidden="true" />}{uploading ? "Uploading" : "Upload document"}</button></form></section>;
}

function KnowledgeFilters({ query, setQuery, statusFilter, setStatusFilter, sortKey, setSortKey, viewMode, setViewMode }: { query: string; setQuery: (value: string) => void; statusFilter: StatusFilter; setStatusFilter: (value: StatusFilter) => void; sortKey: SortKey; setSortKey: (value: SortKey) => void; viewMode: ViewMode; setViewMode: (value: ViewMode) => void }) {
  return <div className="knowledgeFilters" aria-label="Knowledge filters"><label className="knowledgeSearch"><Search size={15} aria-hidden="true" /><span className="sr-only">Search documents</span><input value={query} onChange={(event) => setQuery(event.currentTarget.value)} placeholder="Search sources" /></label><label><Filter size={15} aria-hidden="true" /><span className="sr-only">Filter by status</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.currentTarget.value as StatusFilter)}><option value="all">All statuses</option><option value="ready">Ready</option><option value="processing">Processing</option><option value="failed">Failed</option><option value="archived">Archived</option></select></label><label><ChevronDown size={15} aria-hidden="true" /><span className="sr-only">Sort documents</span><select value={sortKey} onChange={(event) => setSortKey(event.currentTarget.value as SortKey)}><option value="updated">Last updated</option><option value="name">Name</option><option value="status">Status</option></select></label><div className="knowledgeViewToggle" role="group" aria-label="Document view"><button type="button" aria-pressed={viewMode === "table"} onClick={() => setViewMode("table")}>Table</button><button type="button" aria-pressed={viewMode === "cards"} onClick={() => setViewMode("cards")}>Cards</button></div></div>;
}

function DocumentTable({ documents, details, selectedDocumentId, loadingDetails, menuDocumentId, setMenuDocumentId, onDetails, onArchive }: { documents: DocumentRecord[]; details: Record<string, DetailState>; selectedDocumentId: string; loadingDetails: Record<string, boolean>; menuDocumentId: string | null; setMenuDocumentId: (id: string | null) => void; onDetails: (document: DocumentRecord) => void; onArchive: (document: DocumentRecord) => void }) {
  return <div className="knowledgeTableWrap"><table className="knowledgeTable premiumKnowledgeTable"><thead><tr><th scope="col">Document</th><th scope="col">Source</th><th scope="col">Lifecycle</th><th scope="col">Version</th><th scope="col">Size</th><th scope="col">Uploaded</th><th scope="col">Indexed</th><th scope="col">Chunks</th><th scope="col">Actions</th></tr></thead><tbody>{documents.map((document) => <DocumentRow key={document.id} document={document} detail={details[document.id]} selected={selectedDocumentId === document.id} loading={Boolean(loadingDetails[document.id])} menuOpen={menuDocumentId === document.id} setMenuOpen={(open) => setMenuDocumentId(open ? document.id : null)} onDetails={() => onDetails(document)} onArchive={() => onArchive(document)} />)}</tbody></table></div>;
}

function DocumentRow({ document, detail, selected, loading, menuOpen, setMenuOpen, onDetails, onArchive }: { document: DocumentRecord; detail: DetailState | undefined; selected: boolean; loading: boolean; menuOpen: boolean; setMenuOpen: (open: boolean) => void; onDetails: () => void; onArchive: () => void }) {
  const version = activeVersionFor(document, detail?.versions ?? []);
  const chunks = detail?.chunks ?? [];
  return <tr className={selected ? "knowledgeSelectedRow" : undefined}><td><strong>{document.title}</strong><span>{document.category || "Uncategorised"}</span></td><td>{document.source_type}</td><td><DocumentStatusBadge status={document.status} /></td><td>{version ? `v${version.version_number}` : "None"}</td><td>{formatBytes(numberMetadata(version?.metadata_json, "file_size_bytes") ?? numberMetadata(document.metadata_json, "file_size_bytes"))}</td><td>{formatDate(document.created_at)}</td><td>{latestIndexedAt(chunks) ? formatDate(latestIndexedAt(chunks) as string) : "Not indexed"}</td><td>{chunks.length || "-"}</td><td><DocumentActions title={document.title} loading={loading} canArchive={document.status === "ready"} menuOpen={menuOpen} setMenuOpen={setMenuOpen} onDetails={onDetails} onArchive={onArchive} /></td></tr>;
}

function DocumentCard({ document, detail, selected, loading, menuOpen, setMenuOpen, onDetails, onArchive, index }: { document: DocumentRecord; detail: DetailState | undefined; selected: boolean; loading: boolean; menuOpen: boolean; setMenuOpen: (open: boolean) => void; onDetails: () => void; onArchive: () => void; index: number }) {
  const version = activeVersionFor(document, detail?.versions ?? []);
  const chunks = detail?.chunks ?? [];
  return <motion.article className={selected ? "knowledgeDocumentCard selected" : "knowledgeDocumentCard"} role="listitem" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.025 }}><div className="knowledgeDocumentTop"><span className="knowledgeDocumentIcon"><FileText size={18} aria-hidden="true" /></span><DocumentStatusBadge status={document.status} /></div><h4>{document.title}</h4><p>{document.category || "Uncategorised"} - {document.source_type}</p><dl><div><dt>Version</dt><dd>{version ? `v${version.version_number}` : "None"}</dd></div><div><dt>Chunks</dt><dd>{chunks.length || "-"}</dd></div><div><dt>Updated</dt><dd>{formatDate(document.updated_at)}</dd></div><div><dt>Size</dt><dd>{formatBytes(numberMetadata(version?.metadata_json, "file_size_bytes") ?? numberMetadata(document.metadata_json, "file_size_bytes"))}</dd></div></dl><DocumentActions title={document.title} loading={loading} canArchive={document.status === "ready"} menuOpen={menuOpen} setMenuOpen={setMenuOpen} onDetails={onDetails} onArchive={onArchive} /></motion.article>;
}

function DocumentActions({ title, loading, canArchive, menuOpen, setMenuOpen, onDetails, onArchive }: { title: string; loading: boolean; canArchive: boolean; menuOpen: boolean; setMenuOpen: (open: boolean) => void; onDetails: () => void; onArchive: () => void }) {
  return <div className="knowledgeActions"><button className="knowledgeButton small" type="button" onClick={onDetails} aria-label={`View details for ${title}`}>{loading ? <Loader2 className="spinIcon" size={15} aria-hidden="true" /> : <ExternalLink size={15} aria-hidden="true" />}{loading ? "Loading" : "Details"}</button><div className="knowledgeMenu"><button className="knowledgeIconButton" type="button" aria-haspopup="menu" aria-expanded={menuOpen} aria-label={`More actions for ${title}`} onClick={() => setMenuOpen(!menuOpen)}><MoreHorizontal size={17} aria-hidden="true" /></button>{menuOpen ? <div className="knowledgeMenuList" role="menu"><button type="button" role="menuitem" disabled={!canArchive} onClick={() => { setMenuOpen(false); onArchive(); }}><Archive size={14} aria-hidden="true" />Archive</button><span role="note">Retry and hard delete are not supported by the current API.</span></div> : null}</div></div>;
}

function DocumentDetailPanel({ document, assistantId, details, activeVersion, loading, busyAction, onLoad, onExtract, onChunk, onEmbed, onArchive }: { document: DocumentRecord; assistantId: string; details: DetailState | undefined; activeVersion: DocumentVersionRecord | null; loading: boolean; busyAction: string | null; onLoad: () => void; onExtract: () => void; onChunk: () => void; onEmbed: () => void; onArchive: () => void }) {
  const chunks = details?.chunks ?? [];
  const canExtract = activeVersion?.processing_status === "uploaded";
  const canChunk = activeVersion?.processing_status === "ready" && Boolean(activeVersion.extracted_text_path) && chunks.length === 0;
  const canEmbed = activeVersion?.processing_status === "ready" && chunks.length > 0 && chunks.some((chunk) => !chunk.embedding_created_at);
  const canArchive = document.status === "ready";
  return <motion.section className="knowledgePanel knowledgeDetailPanel premiumKnowledgeDetail" aria-labelledby="detail-title" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}><div className="knowledgePanelHeader"><div><p>Selected source</p><h3 id="detail-title">{document.title}</h3></div><button className="knowledgeButton secondary" type="button" onClick={onLoad}>{loading ? <Loader2 className="spinIcon" size={16} aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}{loading ? "Loading" : "Load details"}</button></div><ProcessingTimeline document={document} version={activeVersion} chunks={chunks} /><dl className="knowledgeFacts"><div><dt>Assistant context</dt><dd>{assistantId}</dd></div><div><dt>Source key</dt><dd>{document.source_key || "None"}</dd></div><div><dt>Visibility</dt><dd>{document.visibility}</dd></div><div><dt>Updated</dt><dd>{formatDate(document.updated_at)}</dd></div></dl><div className="knowledgeActionBar" aria-label="Supported document actions"><button className="knowledgeButton primary" type="button" onClick={onExtract} disabled={!canExtract || busyAction === "extract"}>{busyAction === "extract" ? <Loader2 className="spinIcon" size={16} aria-hidden="true" /> : <FileText size={16} aria-hidden="true" />}{busyAction === "extract" ? "Extracting" : "Extract"}</button><button className="knowledgeButton secondary" type="button" onClick={onChunk} disabled={!canChunk || busyAction === "chunk"}>{busyAction === "chunk" ? <Loader2 className="spinIcon" size={16} aria-hidden="true" /> : <Layers3 size={16} aria-hidden="true" />}{busyAction === "chunk" ? "Chunking" : "Chunk"}</button><button className="knowledgeButton secondary" type="button" onClick={onEmbed} disabled={!canEmbed || busyAction === "embed"}>{busyAction === "embed" ? <Loader2 className="spinIcon" size={16} aria-hidden="true" /> : <Database size={16} aria-hidden="true" />}{busyAction === "embed" ? "Indexing" : "Embed"}</button><button className="knowledgeButton danger" type="button" onClick={onArchive} disabled={!canArchive}><Archive size={16} aria-hidden="true" />Archive</button></div><p className="knowledgeUnsupported"><Info size={14} aria-hidden="true" />Only lifecycle actions supported by the current version state are enabled. Failed-version retry and raw text download are not exposed by the current API.</p>{activeVersion ? <div className="knowledgeDetailGrid"><section><h4>Versions</h4><div className="knowledgeVersionList" role="list">{(details?.versions ?? [activeVersion]).map((version) => <article className="knowledgeVersionItem" role="listitem" key={version.id}><div className="knowledgeVersionTitle"><strong>Version {version.version_number}</strong><DocumentStatusBadge status={version.processing_status} /></div>{version.processing_error ? <p className="errorText">{version.processing_error}</p> : null}<dl className="knowledgeFacts compactFacts"><div><dt>Checksum</dt><dd>{version.checksum}</dd></div><div><dt>Original file</dt><dd>{version.original_file_path || "Not stored"}</dd></div><div><dt>Extracted text</dt><dd>{version.extracted_text_path || "Not extracted"}</dd></div><div><dt>Metadata</dt><dd>{metadataSummary(version.metadata_json)}</dd></div></dl></article>)}</div></section><section><h4>Chunk preview</h4>{chunks.length === 0 ? <p className="knowledgeMuted">No chunks are available for the active version.</p> : null}<div className="knowledgeChunkList" role="list">{chunks.slice(0, 6).map((chunk) => <article className="knowledgeChunkItem" role="listitem" key={chunk.id}><strong>Chunk {chunk.chunk_index + 1}</strong><p>{chunk.content}</p><dl className="knowledgeFacts compactFacts"><div><dt>Tokens</dt><dd>{chunk.token_count ?? "Unknown"}</dd></div><div><dt>Embedding</dt><dd>{chunk.embedding_created_at ? `${chunk.embedding_provider || "provider"} at ${formatDate(chunk.embedding_created_at)}` : "Not embedded"}</dd></div><div><dt>Status</dt><dd>{chunk.status}</dd></div></dl></article>)}</div></section></div> : <p className="knowledgeMuted">Load details to inspect versions, metadata, lifecycle, and chunks.</p>}</motion.section>;
}

function ProcessingTimeline({ document, version, chunks }: { document: DocumentRecord; version: DocumentVersionRecord | null; chunks: ChunkRecord[] }) {
  const current = timelineIndex(document, version, chunks);
  const failed = FAILED_STATUSES.has(document.status) || FAILED_STATUSES.has(version?.processing_status ?? "");
  return <div className="processingTimeline" aria-label="Document processing lifecycle">{TIMELINE_STAGES.map((stage, index) => { const state = failed && index >= current ? "failed" : index < current ? "complete" : index === current ? "current" : "pending"; return <div className={`timelineStage ${state}`} key={stage}><span aria-hidden="true">{state === "complete" ? <CheckCircle2 size={15} /> : state === "failed" ? <XCircle size={15} /> : index === current ? <Clock3 size={15} /> : <span className="timelineDot" />}</span><strong>{stage}</strong><small>{state === "complete" ? "Complete" : state === "failed" ? "Failed" : state === "current" ? "Current" : "Pending"}</small></div>; })}</div>;
}

function KnowledgeEmptyState({ onAdd }: { onAdd: () => void }) {
  return <div className="knowledgeEmptyState flagship"><div className="knowledgeEmptyGraphic" aria-hidden="true"><FolderOpen size={34} /><span /><span /></div><h3>Create your assistant knowledge base</h3><p>Upload trusted PDFs, DOCX files, or TXT sources so Conversa can ground answers in approved business knowledge.</p><button className="knowledgeButton primary" type="button" onClick={onAdd}><UploadCloud size={16} aria-hidden="true" />Add Knowledge</button></div>;
}

export function KnowledgeBaseSkeleton() {
  return <section className="knowledgeBasePage premiumKnowledgePage" aria-label="Knowledge base loading"><div className="knowledgeSkeleton hero" /><div className="knowledgeMetrics">{Array.from({ length: 6 }).map((_, index) => <div className="knowledgeMetricCard skeleton" key={index} />)}</div><div className="knowledgeSkeleton grid" /></section>;
}

export function KnowledgeBaseErrorState({ message, retryHref }: { message: string; retryHref: string }) {
  return <section className="knowledgeBasePage premiumKnowledgePage"><div className="knowledgeEmptyState compact" role="alert"><XCircle size={30} aria-hidden="true" /><h2>Knowledge could not be loaded</h2><p>{message}</p><Link className="knowledgeButton primary" href={retryHref}>Retry</Link></div></section>;
}

function DocumentStatusBadge({ status }: { status: string }) {
  const normalised = status.replaceAll("_", " ");
  const tone = FAILED_STATUSES.has(status) ? "failed" : PROCESSING_STATUSES.has(status) ? "processing" : status === "archived" ? "archived" : READY_STATUSES.has(status) ? "ready" : "neutral";
  const Icon = tone === "failed" ? XCircle : tone === "processing" ? Clock3 : tone === "ready" ? CheckCircle2 : Info;
  return <span className={`statusBadge premiumDocumentStatus status-${tone}`} aria-label={`Status: ${normalised}`}><Icon size={13} aria-hidden="true" />{normalised}</span>;
}

function activeVersionFor(document: DocumentRecord, versions: DocumentVersionRecord[]) {
  return versions.find((version) => version.id === document.active_document_version_id) ?? versions[0] ?? null;
}

function buildSummary(documents: DocumentRecord[], details: Record<string, DetailState>) {
  const total = documents.length;
  const ready = documents.filter((document) => READY_STATUSES.has(document.status) || READY_STATUSES.has(activeVersionFor(document, details[document.id]?.versions ?? [])?.processing_status ?? "")).length;
  const processing = documents.filter((document) => PROCESSING_STATUSES.has(document.status) || PROCESSING_STATUSES.has(activeVersionFor(document, details[document.id]?.versions ?? [])?.processing_status ?? "")).length;
  const failed = documents.filter((document) => FAILED_STATUSES.has(document.status) || FAILED_STATUSES.has(activeVersionFor(document, details[document.id]?.versions ?? [])?.processing_status ?? "")).length;
  const chunks = Object.values(details).reduce((totalChunks, detail) => totalChunks + detail.chunks.length, 0);
  const updatedAt = documents.map((document) => document.updated_at).sort().at(-1) ?? null;
  return { total, ready, processing, failed, chunks, updatedAt };
}

function filterAndSortDocuments(documents: DocumentRecord[], details: Record<string, DetailState>, query: string, statusFilter: StatusFilter, sortKey: SortKey) {
  const term = query.trim().toLowerCase();
  return [...documents].filter((document) => {
    const haystack = [document.title, document.category, document.source_type, document.source_key].filter(Boolean).join(" ").toLowerCase();
    const matchesQuery = !term || haystack.includes(term);
    const status = statusGroup(document, details[document.id]);
    return matchesQuery && (statusFilter === "all" || statusFilter === status);
  }).sort((a, b) => sortKey === "name" ? a.title.localeCompare(b.title) : sortKey === "status" ? a.status.localeCompare(b.status) || a.title.localeCompare(b.title) : new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
}

function statusGroup(document: DocumentRecord, detail: DetailState | undefined): Exclude<StatusFilter, "all"> {
  const versionStatus = activeVersionFor(document, detail?.versions ?? [])?.processing_status ?? "";
  if (document.status === "archived") return "archived";
  if (FAILED_STATUSES.has(document.status) || FAILED_STATUSES.has(versionStatus)) return "failed";
  if (PROCESSING_STATUSES.has(document.status) || PROCESSING_STATUSES.has(versionStatus)) return "processing";
  return "ready";
}

function timelineIndex(document: DocumentRecord, version: DocumentVersionRecord | null, chunks: ChunkRecord[]) {
  if (!version) return document.status === "uploaded" ? 0 : 1;
  if (chunks.some((chunk) => chunk.embedding_created_at)) return 6;
  if (chunks.length > 0) return 5;
  if (version.extracted_text_path && version.processing_status === "ready") return 3;
  if (version.extracted_text_path) return 2;
  if (version.processing_status === "uploaded") return 0;
  if (["extracting", "processing", "pending", "queued"].includes(version.processing_status)) return 1;
  if (version.processing_status === "chunking") return 3;
  if (version.processing_status === "embedding") return 5;
  if (READY_STATUSES.has(version.processing_status)) return 6;
  return 1;
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
