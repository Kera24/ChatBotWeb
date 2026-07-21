"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { isDashboardApiError } from "../../lib/api/errors";
import {
  addWidgetOrigin,
  createWidgetPreviewGrant,
  getWidgetDetail,
  getWidgetEmbed,
  getWidgetInstallationStatus,
  getWidgetRevision,
  getWidgetDraft,
  listWidgetOrigins,
  listWidgetRevisions,
  publishWidget,
  removeWidgetOrigin,
  rollbackWidget,
  rotateWidgetPublicKey,
  updateWidgetDraft,
  updateWidgetEmbedPreference,
  updateWidgetKnowledgeScope,
  validateWidgetPublish,
  type WidgetConfigurationPayload,
  type WidgetDetail,
  type WidgetEmbedMetadata,
  type WidgetInstallationStatus,
  type WidgetKnowledgeOption,
  type WidgetOrigin,
  type WidgetPreviewGrant,
  type WidgetPublishValidationResult,
  type WidgetRevisionDetail,
  type WidgetSupportedSdkVersionsResponse,
} from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { WidgetReadinessList, WidgetStatusBadge } from "./widget-status";

type TabId = "overview" | "appearance" | "conversation" | "knowledge" | "domains" | "preview" | "publish" | "history" | "embed";

type DraftForm = WidgetConfigurationPayload;

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "appearance", label: "Appearance" },
  { id: "conversation", label: "Conversation" },
  { id: "knowledge", label: "Knowledge" },
  { id: "domains", label: "Domains" },
  { id: "preview", label: "Preview" },
  { id: "publish", label: "Publish" },
  { id: "history", label: "History" },
  { id: "embed", label: "Embed" },
];

export function WidgetDetailClient({
  session,
  initialWidget,
  initialDraft,
  initialOrigins,
  initialEmbed,
  sdkVersions,
  knowledgeOptions,
  initialRevisions,
  initialInstallationStatus,
}: {
  session: DevelopmentDashboardSession;
  initialWidget: WidgetDetail;
  initialDraft: WidgetRevisionDetail;
  initialOrigins: WidgetOrigin[];
  initialEmbed: WidgetEmbedMetadata;
  sdkVersions: WidgetSupportedSdkVersionsResponse;
  knowledgeOptions: WidgetKnowledgeOption[];
  initialRevisions: WidgetRevisionDetail[];
  initialInstallationStatus: WidgetInstallationStatus[];
}) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [widget, setWidget] = useState(initialWidget);
  const [draft, setDraft] = useState(initialDraft);
  const [savedDraft, setSavedDraft] = useState(initialDraft.configuration);
  const [form, setForm] = useState<DraftForm>(initialDraft.configuration);
  const [origins, setOrigins] = useState(initialOrigins);
  const [embed, setEmbed] = useState(initialEmbed);
  const [revisions, setRevisions] = useState(initialRevisions);
  const [installationStatus, setInstallationStatus] = useState(initialInstallationStatus);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(savedDraft), [form, savedDraft]);

  useEffect(() => {
    if (!dirty) return undefined;
    function beforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  async function saveDraft(fields: Partial<DraftForm>) {
    setSaving(true);
    setError(null);
    setNotice(null);
    setConflict(false);
    try {
      const response = await updateWidgetDraft(session, widget.id, {
        ...fields,
        expected_concurrency_version: draft.concurrency_version,
      });
      setDraft(response.data);
      setSavedDraft(response.data.configuration);
      setForm(response.data.configuration);
      setNotice("Draft saved. Public widget output is unchanged until a publish workflow runs.");
      router.refresh();
    } catch (caught) {
      if (isDashboardApiError(caught) && caught.kind === "conflict") {
        setConflict(true);
        setError("The saved draft changed before this form was submitted. Reload the latest draft before saving again.");
      } else {
        setError(messageForError(caught, "Draft could not be saved."));
      }
    } finally {
      setSaving(false);
    }
  }

  async function reloadDraft() {
    setError(null);
    setNotice(null);
    const response = await getWidgetDraft(session, widget.id);
    setDraft(response.data);
    setSavedDraft(response.data.configuration);
    setForm(response.data.configuration);
    setConflict(false);
  }

  function acceptDraft(nextDraft: WidgetRevisionDetail) {
    setDraft(nextDraft);
    setSavedDraft(nextDraft.configuration);
    setForm(nextDraft.configuration);
  }
  function resetDraft() {
    setForm(savedDraft);
    setError(null);
    setNotice("Local edits were discarded. The saved draft remains unchanged.");
  }

  function updateForm<K extends keyof DraftForm>(key: K, value: DraftForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function refreshWidgetState() {
    const [detailResponse, draftResponse, embedResponse, revisionResponse] = await Promise.all([
      getWidgetDetail(session, widget.id),
      getWidgetDraft(session, widget.id),
      getWidgetEmbed(session, widget.id),
      listWidgetRevisions(session, widget.id),
    ]);
    setWidget(detailResponse.data);
    acceptDraft(draftResponse.data);
    setEmbed(embedResponse.data);
    setRevisions(revisionResponse.data);
    router.refresh();
  }
  async function refreshEmbedAndOrigins() {
    const [originResponse, embedResponse, installationResponse] = await Promise.all([
      listWidgetOrigins(session, widget.id),
      getWidgetEmbed(session, widget.id),
      getWidgetInstallationStatus(session, widget.id),
    ]);
    setOrigins(originResponse.data);
    setEmbed(embedResponse.data);
    setInstallationStatus(installationResponse.data);
  }

  async function refreshInstallationStatus() {
    const response = await getWidgetInstallationStatus(session, widget.id);
    setInstallationStatus(response.data);
  }

  return (
    <section className="widgetAdminPage" aria-labelledby="widget-title">
      <div className="widgetHero">
        <div>
          <p className="eyebrow">Widget administration</p>
          <h2 id="widget-title">{widget.display_name}</h2>
          <p>You are editing saved draft settings. Save does not publish, enable pilot traffic, or deploy runtime changes.</p>
        </div>
        <div className="widgetHeroAside">
          <strong>{origins.filter((origin) => origin.active).length}</strong>
          <span>active allowed domains</span>
        </div>
      </div>

      <div className="widgetTabList" role="tablist" aria-label="Widget settings sections">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className="widgetTab"
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {notice ? <p className="widgetNotice" role="status">{notice}</p> : null}
      {error ? <p className="errorText" role="alert">{error}</p> : null}

      {activeTab === "overview" ? (
        <OverviewPanel widget={widget} draft={draft} dirty={dirty} origins={origins} embed={embed} installationStatus={installationStatus} />
      ) : null}

      {activeTab === "appearance" ? (
        <AppearancePanel form={form} dirty={dirty} saving={saving} conflict={conflict} updateForm={updateForm} saveDraft={saveDraft} reloadDraft={reloadDraft} resetDraft={resetDraft} />
      ) : null}

      {activeTab === "conversation" ? (
        <ConversationPanel form={form} dirty={dirty} saving={saving} conflict={conflict} updateForm={updateForm} saveDraft={saveDraft} reloadDraft={reloadDraft} resetDraft={resetDraft} />
      ) : null}

      {activeTab === "knowledge" ? (
        <KnowledgePanel key={`${draft.id}-${draft.concurrency_version}`} session={session} widgetId={widget.id} draft={draft} options={knowledgeOptions} acceptDraft={acceptDraft} setError={setError} setNotice={setNotice} />
      ) : null}

      {activeTab === "preview" ? (
        <PreviewPanel session={session} widgetId={widget.id} draft={draft} setError={setError} setNotice={setNotice} />
      ) : null}

      {activeTab === "publish" ? (
        <PublishPanel session={session} widget={widget} draft={draft} origins={origins} onPublished={refreshWidgetState} setError={setError} setNotice={setNotice} />
      ) : null}

      {activeTab === "history" ? (
        <HistoryPanel session={session} widget={widget} revisions={revisions} onRolledBack={refreshWidgetState} setError={setError} setNotice={setNotice} />
      ) : null}
      {activeTab === "domains" ? (
        <DomainsPanel session={session} widgetId={widget.id} origins={origins} setOrigins={setOrigins} refreshEmbedAndOrigins={refreshEmbedAndOrigins} setError={setError} setNotice={setNotice} />
      ) : null}

      {activeTab === "embed" ? (
        <EmbedPanel
          session={session}
          widget={widget}
          setWidget={setWidget}
          embed={embed}
          setEmbed={setEmbed}
          sdkVersions={sdkVersions}
          installationStatus={installationStatus}
          refreshInstallationStatus={refreshInstallationStatus}
          setError={setError}
          setNotice={setNotice}
        />
      ) : null}
    </section>
  );
}

function OverviewPanel({ widget, draft, dirty, origins, embed, installationStatus }: { widget: WidgetDetail; draft: WidgetRevisionDetail; dirty: boolean; origins: WidgetOrigin[]; embed: WidgetEmbedMetadata; installationStatus: WidgetInstallationStatus[] }) {
  return (
    <div className="widgetGrid">
      <section className="widgetPanel">
        <h2>Status</h2>
        <div className="widgetStatusCluster">
          <WidgetStatusBadge label="Publication" value={widget.publication_status} />
          <WidgetStatusBadge label="Operational" value={widget.operational_status} />
          <WidgetStatusBadge label="Pilot" value={widget.pilot_status} />
          <WidgetStatusBadge label="Release" value={widget.release_channel} />
        </div>
        <WidgetReadinessList readiness={embed.readiness} />
      </section>
      <section className="widgetPanel">
        <h2>Draft and published revisions</h2>
        <dl className="widgetFacts compactFacts">
          <div><dt>Draft revision</dt><dd>Revision {draft.revision_number}</dd></div>
          <div><dt>Saved draft state</dt><dd>{dirty ? "Unsaved local edits" : "Clean"}</dd></div>
          <div><dt>Published revision</dt><dd>{widget.active_revision_number ? `Revision ${widget.active_revision_number}` : "None"}</dd></div>
          <div><dt>Public key fingerprint</dt><dd>{fingerprint(embed.public_key)}</dd></div>
          <div><dt>Active origins</dt><dd>{origins.filter((origin) => origin.active).length}</dd></div>
          <div><dt>Observed installations</dt><dd>{installationStatus.filter((item) => item.status === "observed").length}</dd></div>
        </dl>
      </section>
    </div>
  );
}

function AppearancePanel(props: FormPanelProps) {
  const { form, updateForm, saveDraft } = props;
  return (
    <form className="widgetForm" onSubmit={(event) => { event.preventDefault(); void saveDraft(pickAppearance(form)); }}>
      <PanelHeader title="Appearance settings" dirty={props.dirty} conflict={props.conflict} />
      <div className="formGrid">
        <TextField id="bot-name" label="Bot name" value={form.bot_name} maxLength={120} onChange={(value) => updateForm("bot_name", value)} />
        <TextField id="launcher-label" label="Launcher label" value={form.launcher_label} maxLength={80} onChange={(value) => updateForm("launcher_label", value)} />
        <ColourField id="primary-colour" label="Primary colour" value={form.primary_colour} onChange={(value) => updateForm("primary_colour", value)} />
        <ColourField id="secondary-colour" label="Secondary colour" value={form.secondary_colour || ""} onChange={(value) => updateForm("secondary_colour", value || null)} optional />
        <SelectField id="theme-mode" label="Theme mode" value={form.theme_mode} options={["system", "light", "dark"]} onChange={(value) => updateForm("theme_mode", value)} />
        <SelectField id="position" label="Position" value={form.position} options={["bottom_right", "bottom_left"]} onChange={(value) => updateForm("position", value)} />
        <TextField id="logo-url" label="Logo URL" value={form.logo_path || ""} maxLength={512} onChange={(value) => updateForm("logo_path", value || null)} optional helper="Use an HTTPS raster URL. Uploads are not part of this task." />
        <TextField id="avatar-url" label="Avatar URL" value={form.avatar_path || ""} maxLength={512} onChange={(value) => updateForm("avatar_path", value || null)} optional helper="SVG, data, and script-like URLs are rejected by the backend/runtime contract." />
      </div>
      <p className="mutedText">Widget colours may be adjusted by the runtime to preserve accessible contrast.</p>
      <FormActions {...props} />
    </form>
  );
}

function ConversationPanel(props: FormPanelProps) {
  const { form, updateForm, saveDraft } = props;
  const questions = form.suggested_questions_json || [];
  return (
    <form className="widgetForm" onSubmit={(event) => { event.preventDefault(); void saveDraft(pickConversation(form)); }}>
      <PanelHeader title="Conversation settings" dirty={props.dirty} conflict={props.conflict} />
      <div className="formGrid">
        <TextAreaField id="welcome-message" label="Welcome message" value={form.welcome_message} maxLength={500} onChange={(value) => updateForm("welcome_message", value)} />
        <TextField id="language" label="Language" value={form.language} maxLength={16} onChange={(value) => updateForm("language", value)} helper="Use a short language code such as en." />
        <TextAreaField id="privacy-notice" label="Privacy notice" value={form.privacy_notice_text || ""} maxLength={1000} onChange={(value) => updateForm("privacy_notice_text", value || null)} optional />
        <TextField id="privacy-url" label="Privacy URL" value={form.privacy_notice_url || ""} maxLength={512} onChange={(value) => updateForm("privacy_notice_url", value || null)} optional />
        <TextField id="terms-url" label="Terms URL" value={form.terms_url || ""} maxLength={512} onChange={(value) => updateForm("terms_url", value || null)} optional />
        <TextField id="fallback-contact" label="Fallback contact text" value={form.fallback_contact_text || ""} maxLength={500} onChange={(value) => updateForm("fallback_contact_text", value || null)} optional />
      </div>

      <fieldset className="widgetFieldset">
        <legend>Suggested questions</legend>
        <p className="mutedText">Up to six saved suggestions. Runtime layout may show fewer on smaller screens.</p>
        <div className="suggestionEditor">
          {questions.map((question, index) => (
            <div className="suggestionRow" key={`${index}-${question}`}>
              <label className="srOnly" htmlFor={`suggestion-${index}`}>Suggested question {index + 1}</label>
              <input id={`suggestion-${index}`} value={question} maxLength={120} onChange={(event) => updateQuestion(index, event.target.value)} />
              <button type="button" className="smallButton" onClick={() => moveQuestion(index, -1)} disabled={index === 0}>Up</button>
              <button type="button" className="smallButton" onClick={() => moveQuestion(index, 1)} disabled={index === questions.length - 1}>Down</button>
              <button type="button" className="smallButton dangerButton" onClick={() => removeQuestion(index)}>Remove</button>
            </div>
          ))}
          <button type="button" className="actionButton" onClick={() => updateForm("suggested_questions_json", [...questions, ""])} disabled={questions.length >= 6}>Add question</button>
          <span className="mutedText">{6 - questions.length} slots remaining</span>
        </div>
      </fieldset>

      <div className="checkboxGrid">
        <label><input type="checkbox" checked={form.show_citations} onChange={(event) => updateForm("show_citations", event.target.checked)} /> Show citations when available</label>
        <label><input type="checkbox" checked={form.allow_conversation_history} onChange={(event) => updateForm("allow_conversation_history", event.target.checked)} /> Allow conversation history capability flag</label>
      </div>
      <FormActions {...props} />
    </form>
  );

  function updateQuestion(index: number, value: string) {
    updateForm("suggested_questions_json", questions.map((item, itemIndex) => (itemIndex === index ? value : item)));
  }
  function removeQuestion(index: number) {
    updateForm("suggested_questions_json", questions.filter((_, itemIndex) => itemIndex !== index));
  }
  function moveQuestion(index: number, direction: -1 | 1) {
    const next = [...questions];
    const swap = index + direction;
    if (swap < 0 || swap >= next.length) return;
    [next[index], next[swap]] = [next[swap], next[index]];
    updateForm("suggested_questions_json", next);
  }
}

function KnowledgePanel({ session, widgetId, draft, options, acceptDraft, setError, setNotice }: {
  session: DevelopmentDashboardSession;
  widgetId: string;
  draft: WidgetRevisionDetail;
  options: WidgetKnowledgeOption[];
  acceptDraft: (draft: WidgetRevisionDetail) => void;
  setError: (message: string | null) => void;
  setNotice: (message: string | null) => void;
}) {
  const [selected, setSelected] = useState<string[]>(draft.configuration.knowledge_scope_json || []);
  const [pending, setPending] = useState(false);
  const dirty = JSON.stringify([...selected].sort()) !== JSON.stringify([...(draft.configuration.knowledge_scope_json || [])].sort());

  async function save() {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await updateWidgetKnowledgeScope(session, widgetId, { document_ids: selected, expected_concurrency_version: draft.concurrency_version });
      acceptDraft(response.data);
      setNotice("Knowledge scope saved to the draft. Public retrieval remains unchanged until publish.");
    } catch (caught) {
      setError(messageForError(caught, "Knowledge scope could not be saved."));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="widgetPanel">
      <h2>Knowledge scope</h2>
      <p className="mutedText">Select tenant-owned resources for the draft. Published revisions freeze this selection until another publish or rollback.</p>
      <div className="knowledgeList" role="list" aria-label="Knowledge resources">
        {options.length === 0 ? <p className="mutedText">No tenant knowledge resources are available for this widget yet.</p> : null}
        {options.map((option) => (
          <label className="knowledgeItem" key={option.id}>
            <input type="checkbox" checked={selected.includes(option.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, option.id] : current.filter((id) => id !== option.id))} />
            <span><strong>{option.title}</strong><small>{option.type} - {option.readiness} - {option.indexing_status}</small></span>
          </label>
        ))}
      </div>
      <div className="formActions">
        <button className="actionButton" type="button" disabled={!dirty || pending} onClick={() => void save()}>{pending ? "Saving" : "Save knowledge scope"}</button>
        <span className="mutedText">{selected.length} selected</span>
      </div>
    </section>
  );
}

function PreviewPanel({ session, widgetId, draft, setError, setNotice }: {
  session: DevelopmentDashboardSession;
  widgetId: string;
  draft: WidgetRevisionDetail;
  setError: (message: string | null) => void;
  setNotice: (message: string | null) => void;
}) {
  const [grant, setGrant] = useState<WidgetPreviewGrant | null>(null);
  const [mode, setMode] = useState<"desktop" | "mobile">("desktop");
  const [pending, setPending] = useState(false);

  async function refreshGrant() {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await createWidgetPreviewGrant(session, widgetId, draft.id);
      setGrant(response.data);
      setNotice("Short-lived preview grant created for this saved draft revision.");
    } catch (caught) {
      setError(messageForError(caught, "Preview grant could not be created."));
    } finally {
      setPending(false);
    }
  }

  const previewConfig = grant?.configuration || draft.configuration;
  return (
    <section className="widgetPanel">
      <div className="panelHeaderLine">
        <div><h2>Draft preview</h2><p>Preview uses a short-lived admin grant bound to this draft revision. It does not publish draft configuration.</p></div>
        <button className="actionButton" type="button" disabled={pending} onClick={() => void refreshGrant()}>{pending ? "Creating" : "Refresh preview grant"}</button>
      </div>
      <div className="previewControls" role="group" aria-label="Preview viewport">
        <button className="smallButton" type="button" aria-pressed={mode === "desktop"} onClick={() => setMode("desktop")}>Desktop</button>
        <button className="smallButton" type="button" aria-pressed={mode === "mobile"} onClick={() => setMode("mobile")}>Mobile</button>
        <span className="mutedText">Draft revision {draft.revision_number}{grant ? ` - expires ${formatDate(grant.expires_at)}` : ""}</span>
      </div>
      <div className={`previewShell ${mode}`}>
        <iframe className="previewFrame" title="Widget draft preview" sandbox="allow-scripts" srcDoc={previewHtml(previewConfig)} />
      </div>
    </section>
  );
}
function PublishPanel({ session, widget, draft, origins, onPublished, setError, setNotice }: {
  session: DevelopmentDashboardSession;
  widget: WidgetDetail;
  draft: WidgetRevisionDetail;
  origins: WidgetOrigin[];
  onPublished: () => Promise<void>;
  setError: (message: string | null) => void;
  setNotice: (message: string | null) => void;
}) {
  const [validation, setValidation] = useState<WidgetPublishValidationResult | null>(null);
  const [pending, setPending] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function validate() {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await validateWidgetPublish(session, widget.id, { draft_revision_id: draft.id, expected_concurrency_version: draft.concurrency_version });
      setValidation(response.data);
      setNotice(response.data.publishable ? "Draft passed publish validation." : "Draft has publish blockers.");
    } catch (caught) {
      setError(messageForError(caught, "Publish validation could not run."));
    } finally {
      setPending(false);
    }
  }

  async function publish() {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      await publishWidget(session, widget.id, { draft_revision_id: draft.id, expected_concurrency_version: draft.concurrency_version });
      setConfirmOpen(false);
      await onPublished();
      setNotice("Draft published. A new draft revision is ready for future edits.");
    } catch (caught) {
      setError(messageForError(caught, "Publish failed."));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="widgetPanel">
      <div className="panelHeaderLine">
        <div><h2>Publish</h2><p>Publishing promotes the saved draft to an immutable public revision. Pilot and operational controls are unchanged.</p></div>
        <button className="actionButton" type="button" disabled={pending} onClick={() => void validate()}>{pending ? "Checking" : "Validate publish"}</button>
      </div>
      <dl className="widgetFacts compactFacts"><div><dt>Draft revision</dt><dd>{draft.revision_number}</dd></div><div><dt>Active published revision</dt><dd>{widget.active_revision_number || "None"}</dd></div><div><dt>Active origins</dt><dd>{origins.filter((origin) => origin.active).length}</dd></div></dl>
      {validation ? <ValidationSummary validation={validation} /> : <p className="mutedText">Run validation to review blockers, warnings, knowledge readiness, and draft-to-published changes.</p>}
      <div className="formActions"><button className="actionButton" type="button" disabled={!validation?.publishable || pending} onClick={() => setConfirmOpen(true)}>Publish draft</button></div>
      {confirmOpen ? <div className="dialogBackdrop" role="presentation"><section className="confirmDialog" role="dialog" aria-modal="true" aria-labelledby="publish-title" aria-describedby="publish-description"><h2 id="publish-title">Publish draft revision {draft.revision_number}?</h2><p id="publish-description">This makes the saved draft available through the public configuration endpoint for approved origins. Pilot enablement remains separate.</p><div className="formActions"><button className="actionButton" type="button" autoFocus onClick={() => setConfirmOpen(false)}>Cancel</button><button className="actionButton" type="button" disabled={pending} onClick={() => void publish()}>{pending ? "Publishing" : "Publish"}</button></div></section></div> : null}
    </section>
  );
}

function HistoryPanel({ session, widget, revisions, onRolledBack, setError, setNotice }: {
  session: DevelopmentDashboardSession;
  widget: WidgetDetail;
  revisions: WidgetRevisionDetail[];
  onRolledBack: () => Promise<void>;
  setError: (message: string | null) => void;
  setNotice: (message: string | null) => void;
}) {
  const [detail, setDetail] = useState<WidgetRevisionDetail | null>(null);
  const [pending, setPending] = useState(false);

  async function loadDetail(revisionId: string) {
    setPending(true);
    setError(null);
    try {
      const response = await getWidgetRevision(session, widget.id, revisionId);
      setDetail(response.data);
    } catch (caught) {
      setError(messageForError(caught, "Revision could not be loaded."));
    } finally {
      setPending(false);
    }
  }

  async function rollback(revision: WidgetRevisionDetail) {
    if (!widget.active_published_revision_id) return;
    if (!window.confirm(`Roll back by publishing a new revision cloned from revision ${revision.revision_number}?`)) return;
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      await rollbackWidget(session, widget.id, { target_revision_id: revision.id, expected_active_revision_id: widget.active_published_revision_id });
      await onRolledBack();
      setNotice("Rollback published as a new immutable revision. Historical revisions were not changed.");
    } catch (caught) {
      setError(messageForError(caught, "Rollback failed."));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="widgetGrid">
      <section className="widgetPanel"><h2>Revision history</h2><div className="revisionList" role="list" aria-label="Widget revisions">{revisions.map((revision) => <div className="revisionItem" role="listitem" key={revision.id}><div><strong>Revision {revision.revision_number}</strong><span>{revision.status}{revision.is_active_published ? " - active" : ""} - {formatDate(revision.created_at)}</span></div><div className="formActions compactActions"><button className="smallButton" type="button" disabled={pending} onClick={() => void loadDetail(revision.id)}>View</button>{revision.status === "published" && !revision.is_active_published ? <button className="smallButton" type="button" disabled={pending} onClick={() => void rollback(revision)}>Rollback</button> : null}</div></div>)}</div></section>
      <section className="widgetPanel"><h2>Revision detail</h2>{detail ? <RevisionDetail revision={detail} /> : <p className="mutedText">Select a revision to inspect immutable configuration.</p>}</section>
    </div>
  );
}
function DomainsPanel({ session, widgetId, origins, setOrigins, refreshEmbedAndOrigins, setError, setNotice }: {
  session: DevelopmentDashboardSession;
  widgetId: string;
  origins: WidgetOrigin[];
  setOrigins: (origins: WidgetOrigin[]) => void;
  refreshEmbedAndOrigins: () => Promise<void>;
  setError: (message: string | null) => void;
  setNotice: (message: string | null) => void;
}) {
  const [origin, setOrigin] = useState("https://example.com");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      await addWidgetOrigin(session, widgetId, origin.trim());
      setOrigin("https://example.com");
      await refreshEmbedAndOrigins();
      setNotice("Allowed domain added. The canonical origin is now authorized by the backend.");
    } catch (caught) {
      setError(messageForError(caught, "Origin could not be added."));
    } finally {
      setPending(false);
    }
  }

  async function remove(originId: string) {
    if (pending) return;
    const target = origins.find((item) => item.id === originId);
    if (!target) return;
    if (!window.confirm(`Remove ${target.origin} from this widget's allowed domains?`)) return;
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await removeWidgetOrigin(session, widgetId, originId);
      setOrigins(origins.map((item) => (item.id === originId ? response.data : item)));
      await refreshEmbedAndOrigins();
      setNotice("Allowed domain removed.");
    } catch (caught) {
      setError(messageForError(caught, "Origin could not be removed."));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="widgetPanel">
      <h2>Domains</h2>
      <p className="mutedText">Add exact customer website origins. Wildcards, paths, queries, and fragments are not supported.</p>
      <form className="originForm" onSubmit={submit}>
        <label htmlFor="origin-input">Allowed origin</label>
        <input id="origin-input" value={origin} onChange={(event) => setOrigin(event.target.value)} placeholder="https://example.com" />
        <button className="actionButton" type="submit" disabled={pending}>{pending ? "Saving" : "Add origin"}</button>
      </form>
      <div className="originList" role="list" aria-label="Allowed origins">
        {origins.map((item) => (
          <div className="originItem" role="listitem" key={item.id}>
            <div>
              <strong>{item.origin}</strong>
              <span>{item.active ? "Active" : "Inactive"} - {item.environment}</span>
            </div>
            {item.active ? <button type="button" className="smallButton dangerButton" disabled={pending} onClick={() => void remove(item.id)}>Remove</button> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function EmbedPanel({ session, widget, setWidget, embed, setEmbed, sdkVersions, installationStatus, refreshInstallationStatus, setError, setNotice }: {
  session: DevelopmentDashboardSession;
  widget: WidgetDetail;
  setWidget: (widget: WidgetDetail) => void;
  embed: WidgetEmbedMetadata;
  setEmbed: (embed: WidgetEmbedMetadata) => void;
  sdkVersions: WidgetSupportedSdkVersionsResponse;
  installationStatus: WidgetInstallationStatus[];
  refreshInstallationStatus: () => Promise<void>;
  setError: (message: string | null) => void;
  setNotice: (message: string | null) => void;
}) {
  const [mode, setMode] = useState<"managed_major" | "pinned">(embed.version_mode === "pinned" ? "pinned" : "managed_major");
  const [pinned, setPinned] = useState(embed.pinned_sdk_version || sdkVersions.recommended);
  const [pending, setPending] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [rotateOpen, setRotateOpen] = useState(false);

  async function saveEmbed(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await updateWidgetEmbedPreference(session, widget.id, {
        version_mode: mode,
        pinned_sdk_version: mode === "pinned" ? pinned : null,
      });
      setEmbed(response.data);
      setNotice("Embed version preference updated.");
    } catch (caught) {
      setError(messageForError(caught, "Embed version could not be updated."));
    } finally {
      setPending(false);
    }
  }

  async function rotateKey() {
    if (pending) return;
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const result = await rotateWidgetPublicKey(session, widget.id, widget.public_credential_id);
      const freshEmbed = await getWidgetEmbed(session, widget.id);
      setWidget({ ...widget, public_identifier: result.data.public_key, public_credential_id: result.data.public_credential_id });
      setEmbed(freshEmbed.data);
      setRotateOpen(false);
      setNotice("Public key rotated. Install the new embed snippet on approved domains.");
    } catch (caught) {
      setError(messageForError(caught, "Public key could not be rotated."));
    } finally {
      setPending(false);
    }
  }

  async function copy(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(`${label} copied.`);
    } catch {
      setCopied("Copy failed. Select the text and copy it manually.");
    }
  }

  return (
    <div className="widgetGrid">
      <section className="widgetPanel">
        <h2>Embed setup</h2>
        <div className="widgetStatusCluster">
          <WidgetStatusBadge label="Publication" value={embed.publication_status} />
          <WidgetStatusBadge label="Operational" value={embed.operational_status} />
          <WidgetStatusBadge label="Pilot" value={embed.pilot_status} />
        </div>
        <WidgetReadinessList readiness={embed.readiness} />
        <div className="keyBlock">
          <span>Public widget key</span>
          <code>{embed.public_key}</code>
          <button className="smallButton" type="button" onClick={() => void copy(embed.public_key, "Public key")}>Copy key</button>
        </div>
        <pre className="snippetBlock" tabIndex={0}><code>{embed.snippet}</code></pre>
        <div className="formActions">
          <button className="actionButton" type="button" onClick={() => void copy(embed.snippet, "Embed snippet")}>Copy snippet</button>
          <button className="actionButton dangerAction" type="button" onClick={() => setRotateOpen(true)}>Rotate public key</button>
        </div>
        {copied ? <p className="widgetNotice" role="status">{copied}</p> : null}
      </section>

      <section className="widgetPanel">
        <h2>SDK version</h2>
        <form className="widgetForm compactForm" onSubmit={saveEmbed}>
          <label><input type="radio" checked={mode === "managed_major"} onChange={() => setMode("managed_major")} /> Managed major alias</label>
          <p className="mutedText">Receives compatible updates within protocol major {embed.protocol_major}. No fixed SRI is used for the mutable alias.</p>
          <label><input type="radio" checked={mode === "pinned"} onChange={() => setMode("pinned")} /> Pinned immutable SDK</label>
          <select value={pinned} onChange={(event) => setPinned(event.target.value)} disabled={mode !== "pinned"}>
            {sdkVersions.versions.map((version) => (
              <option key={version.version} value={version.version} disabled={version.support_status !== "supported"}>
                {version.version} - {version.support_status}
              </option>
            ))}
          </select>
          <dl className="widgetFacts compactFacts">
            <div><dt>Selected loader</dt><dd>{embed.selected_loader_path}</dd></div>
            <div><dt>API version</dt><dd>{embed.api_version}</dd></div>
            <div><dt>SRI</dt><dd>{embed.sri || "Not used"}</dd></div>
            <div><dt>Release channel</dt><dd>{embed.release_channel}</dd></div>
          </dl>
          <button className="actionButton" type="submit" disabled={pending}>{pending ? "Saving" : "Save embed version"}</button>
        </form>
      </section>

      <section className="widgetPanel">
        <div className="panelHeaderLine">
          <div><h2>Installation status</h2><p>Observed means the platform has seen a valid widget configuration request from that allowed origin.</p></div>
          <button className="smallButton" type="button" onClick={() => void refreshInstallationStatus()}>Refresh</button>
        </div>
        <InstallationStatusList items={installationStatus} />
      </section>
      {rotateOpen ? (
        <div className="dialogBackdrop" role="presentation">
          <section className="confirmDialog" role="dialog" aria-modal="true" aria-labelledby="rotate-title" aria-describedby="rotate-description">
            <h2 id="rotate-title">Rotate public widget key?</h2>
            <p id="rotate-description">Existing embed snippets using the old key will stop working. Install the new snippet on approved domains after rotation.</p>
            <div className="formActions">
              <button className="actionButton" type="button" onClick={() => setRotateOpen(false)} autoFocus>Cancel</button>
              <button className="actionButton dangerAction" type="button" disabled={pending} onClick={() => void rotateKey()}>{pending ? "Rotating" : "Rotate key"}</button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

function ValidationSummary({ validation }: { validation: WidgetPublishValidationResult }) {
  return (
    <div className="validationSummary">
      <h3>{validation.publishable ? "Ready to publish" : "Publish blockers"}</h3>
      {validation.errors.length ? <ul className="validationList">{validation.errors.map((item) => <li key={`${item.field}-${item.code}`}>{fieldLabel(item.field)}: {item.message}</li>)}</ul> : <p className="mutedText">No blocking validation errors.</p>}
      {validation.warnings.length ? <><h3>Warnings</h3><ul className="validationList">{validation.warnings.map((item) => <li key={`${item.field}-${item.code}`}>{fieldLabel(item.field)}: {item.message}</li>)}</ul></> : null}
      <h3>Changes</h3>
      <DiffList diff={validation.diff} />
      <h3>Knowledge readiness</h3>
      <div className="knowledgeList">{validation.knowledge.length ? validation.knowledge.map((item) => <div className="knowledgeItem static" key={item.id}><span><strong>{item.title}</strong><small>{item.readiness} - {item.indexing_status}</small></span></div>) : <p className="mutedText">No knowledge resources selected.</p>}</div>
    </div>
  );
}

function DiffList({ diff }: { diff: { changed_fields?: string[]; has_published_revision?: boolean } }) {
  const fields = diff.changed_fields || [];
  if (!diff.has_published_revision) return <p className="mutedText">This is the first publication for the widget.</p>;
  if (fields.length === 0) return <p className="mutedText">No field changes detected.</p>;
  return <ul className="diffList">{fields.map((field) => <li key={field}>{fieldLabel(field)} changed</li>)}</ul>;
}

function RevisionDetail({ revision }: { revision: WidgetRevisionDetail }) {
  return <dl className="widgetFacts compactFacts"><div><dt>Status</dt><dd>{revision.status}</dd></div><div><dt>Created</dt><dd>{formatDate(revision.created_at)}</dd></div><div><dt>Published</dt><dd>{revision.published_at ? formatDate(revision.published_at) : "Not published"}</dd></div><div><dt>Bot name</dt><dd>{revision.configuration.bot_name}</dd></div><div><dt>Welcome</dt><dd>{revision.configuration.welcome_message}</dd></div><div><dt>Knowledge resources</dt><dd>{revision.configuration.knowledge_scope_json.length}</dd></div><div><dt>Source revision</dt><dd>{revision.source_revision_id || "None"}</dd></div></dl>;
}

function InstallationStatusList({ items }: { items: WidgetInstallationStatus[] }) {
  return <div className="installationList" role="list" aria-label="Installation observations">{items.length === 0 ? <p className="mutedText">No allowed origins are configured.</p> : null}{items.map((item) => <div className="installationItem" role="listitem" key={item.origin}><strong>{item.origin}</strong><span>{item.status}{item.last_seen_at ? ` - last seen ${formatDate(item.last_seen_at)}` : ""}</span><small>{item.sdk_version ? `SDK ${item.sdk_version}` : "SDK not observed"}</small></div>)}</div>;
}
type FormPanelProps = {
  form: DraftForm;
  dirty: boolean;
  saving: boolean;
  conflict: boolean;
  updateForm: <K extends keyof DraftForm>(key: K, value: DraftForm[K]) => void;
  saveDraft: (fields: Partial<DraftForm>) => Promise<void>;
  reloadDraft: () => Promise<void>;
  resetDraft: () => void;
};

function PanelHeader({ title, dirty, conflict }: { title: string; dirty: boolean; conflict: boolean }) {
  return (
    <div className="panelHeaderLine">
      <div>
        <h2>{title}</h2>
        <p>{dirty ? "Unsaved local edits" : "Saved draft loaded"}{conflict ? " - conflict detected" : ""}</p>
      </div>
    </div>
  );
}

function FormActions({ dirty, saving, conflict, reloadDraft, resetDraft }: FormPanelProps) {
  return (
    <div className="formActions">
      <button className="actionButton" type="submit" disabled={!dirty || saving || conflict}>{saving ? "Saving" : "Save draft"}</button>
      <button className="smallButton" type="button" disabled={!dirty || saving} onClick={resetDraft}>Discard local edits</button>
      {conflict ? <button className="smallButton" type="button" onClick={() => void reloadDraft()}>Reload latest draft</button> : null}
    </div>
  );
}

function TextField({ id, label, value, onChange, maxLength, optional = false, helper }: { id: string; label: string; value: string; onChange: (value: string) => void; maxLength: number; optional?: boolean; helper?: string }) {
  return (
    <div className="formField">
      <label htmlFor={id}>{label}{optional ? " (optional)" : ""}</label>
      <input id={id} value={value} maxLength={maxLength} onChange={(event) => onChange(event.target.value)} />
      <p>{helper || `${value.length}/${maxLength} characters`}</p>
    </div>
  );
}

function TextAreaField({ id, label, value, onChange, maxLength, optional = false }: { id: string; label: string; value: string; onChange: (value: string) => void; maxLength: number; optional?: boolean }) {
  return (
    <div className="formField fullField">
      <label htmlFor={id}>{label}{optional ? " (optional)" : ""}</label>
      <textarea id={id} value={value} maxLength={maxLength} rows={4} onChange={(event) => onChange(event.target.value)} />
      <p>{value.length}/{maxLength} characters</p>
    </div>
  );
}

function ColourField({ id, label, value, onChange, optional = false }: { id: string; label: string; value: string; onChange: (value: string) => void; optional?: boolean }) {
  return (
    <div className="formField colourField">
      <label htmlFor={id}>{label}{optional ? " (optional)" : ""}</label>
      <div>
        <input id={id} value={value} maxLength={16} onChange={(event) => onChange(event.target.value)} />
        <input aria-label={`${label} colour swatch`} type="color" value={isHex(value) ? value : "#111827"} onChange={(event) => onChange(event.target.value)} />
      </div>
    </div>
  );
}

function SelectField({ id, label, value, options, onChange }: { id: string; label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <div className="formField">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option} value={option}>{option.replace(/_/g, " ")}</option>)}
      </select>
    </div>
  );
}

function pickAppearance(form: DraftForm): Partial<DraftForm> {
  return {
    bot_name: form.bot_name,
    launcher_label: form.launcher_label,
    primary_colour: form.primary_colour,
    secondary_colour: form.secondary_colour,
    logo_path: form.logo_path,
    avatar_path: form.avatar_path,
    position: form.position,
    theme_mode: form.theme_mode,
  };
}

function pickConversation(form: DraftForm): Partial<DraftForm> {
  return {
    welcome_message: form.welcome_message,
    suggested_questions_json: form.suggested_questions_json.map((item) => item.trim()).filter(Boolean),
    fallback_contact_text: form.fallback_contact_text,
    privacy_notice_text: form.privacy_notice_text,
    privacy_notice_url: form.privacy_notice_url,
    terms_url: form.terms_url,
    language: form.language,
    show_citations: form.show_citations,
    allow_conversation_history: form.allow_conversation_history,
    max_initial_suggestions: Math.min(6, Math.max(0, form.suggested_questions_json.length)),
  };
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function fieldLabel(field: string) {
  return field.replace(/_json$/, "").replace(/_/g, " ");
}

function escapeText(value: string | null | undefined) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function previewHtml(config: WidgetConfigurationPayload) {
  const align = config.position === "bottom_left" ? "flex-start" : "flex-end";
  const suggestions = (config.suggested_questions_json || []).slice(0, 4).map((question) => `<button type="button">${escapeText(question)}</button>`).join("");
  return `<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#eef2f7;color:#111827}.shell{min-height:100vh;display:flex;align-items:flex-end;justify-content:${align};padding:24px}.panel{width:min(360px,100%);border:1px solid #d6dde8;border-radius:8px;background:white;box-shadow:0 16px 32px rgba(15,23,42,.16);overflow:hidden}.head{background:${escapeText(config.primary_colour)};color:white;padding:16px}.body{padding:16px;display:grid;gap:12px}.suggestions{display:flex;flex-wrap:wrap;gap:8px}.suggestions button{border:1px solid #cbd5e1;background:#f8fafc;border-radius:999px;padding:8px 10px}.composer{border:1px solid #cbd5e1;border-radius:8px;padding:10px;color:#64748b}</style></head><body><main class="shell" aria-label="Widget draft preview"><section class="panel"><div class="head"><strong>${escapeText(config.bot_name)}</strong></div><div class="body"><p>${escapeText(config.welcome_message)}</p><div class="suggestions">${suggestions}</div><div class="composer">${escapeText(config.launcher_label)}</div></div></section></main></body></html>`;
}
function messageForError(error: unknown, fallback: string) {
  if (isDashboardApiError(error)) {
    if (error.kind === "validation") return "The server rejected one or more fields. Check exact origins, URLs, colours, and length limits.";
    if (error.kind === "conflict") return "The request conflicts with current widget state. Reload before trying again.";
    if (error.kind === "forbidden") return "This user cannot perform that widget administration action.";
    if (error.kind === "not_found") return "The widget resource was not found in this workspace.";
    if (error.kind === "network") return "The API could not be reached. Check that the backend is running.";
  }
  return fallback;
}

function fingerprint(value: string) {
  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}

function isHex(value: string) {
  return /^#[0-9a-fA-F]{6}$/.test(value);
}

