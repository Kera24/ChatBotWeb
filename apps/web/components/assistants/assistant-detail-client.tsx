"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  AlertCircle,
  Archive,
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Clock3,
  Copy,
  Database,
  FileText,
  Globe2,
  Loader2,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Rocket,
  Settings,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, type ComponentType } from "react";

import type { OverviewData } from "../../lib/api/overview";
import { archiveWidget, duplicateWidget, type WidgetDetail, type WidgetEmbedMetadata, type WidgetInstallationStatus, type WidgetKnowledgeOption, type WidgetOrigin, type WidgetRevisionDetail, type WidgetSupportedSdkVersionsResponse } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { ChatbotClient } from "../chatbot/chatbot-client";
import { WidgetDetailClient } from "../widgets/widget-detail-client";
import { assistantLifecycle, AssistantStatusBadge } from "./assistant-management";

type AssistantDetailClientProps = {
  session: DevelopmentDashboardSession;
  initialWidget: WidgetDetail;
  initialDraft: WidgetRevisionDetail;
  initialOrigins: WidgetOrigin[];
  initialEmbed: WidgetEmbedMetadata;
  initialSdkVersions: WidgetSupportedSdkVersionsResponse;
  initialKnowledgeOptions: WidgetKnowledgeOption[];
  initialRevisions: WidgetRevisionDetail[];
  initialInstallationStatus: WidgetInstallationStatus[];
  overviewData: OverviewData;
};

type AssistantTab = "overview" | "knowledge" | "playground" | "widget" | "analytics" | "settings";
type PendingAction = "duplicate" | "archive" | null;

type DetailModel = {
  widget: WidgetDetail;
  draft: WidgetRevisionDetail;
  embed: WidgetEmbedMetadata;
  origins: WidgetOrigin[];
  installationStatus: WidgetInstallationStatus[];
  knowledgeOptions: WidgetKnowledgeOption[];
  revisions: WidgetRevisionDetail[];
  overviewData: OverviewData;
  assistantId: string;
  lifecycle: ReturnType<typeof assistantLifecycle>;
  description: string;
  scopedKnowledge: WidgetKnowledgeOption[];
  knowledgeCounts: { total: number; ready: number; processing: number; failed: number };
  conversations: OverviewData["conversations"];
  reviewItems: OverviewData["reviewItems"];
  fallbackOrLowConfidence: number;
  averageLatency: number | null;
  citationCoverage: number | null;
  setupItems: Array<{ label: string; complete: boolean; helper: string }>;
  nextAction: { label: string; href: string; icon: LucideIcon; helper: string };
  recentActivity: Array<{ icon: LucideIcon; label: string; helper: string; time: string | null }>;
};

const tabs: Array<{ id: AssistantTab; label: string; icon: ComponentType<{ size?: number }> }> = [
  { id: "overview", label: "Overview", icon: Bot },
  { id: "knowledge", label: "Knowledge", icon: FileText },
  { id: "playground", label: "Playground", icon: MessageSquare },
  { id: "widget", label: "Widget", icon: Rocket },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "settings", label: "Settings", icon: Settings },
];

export function AssistantDetailClient(props: AssistantDetailClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reduceMotion = useReducedMotion();
  const selected = coerceTab(searchParams.get("tab"));
  const model = useMemo(() => buildDetailModel(props), [props]);
  const [pending, setPending] = useState<PendingAction>(null);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  async function duplicate() {
    setPending("duplicate");
    setNotice(null);
    try {
      const response = await duplicateWidget(props.session, model.assistantId);
      router.push(withAssistantContext(`/assistants/${response.data.id}`, response.data.id));
      router.refresh();
      setPending(null);
    } catch {
      setNotice("Assistant could not be duplicated.");
      setPending(null);
    }
  }

  async function archive() {
    setPending("archive");
    setNotice(null);
    try {
      await archiveWidget(props.session, model.assistantId);
      router.push("/dashboard");
      router.refresh();
    } catch {
      setNotice("Assistant could not be archived.");
      setPending(null);
    }
  }

  return (
    <section className="assistantDetailPage premiumAssistantDetailPage" aria-labelledby="assistant-detail-title">
      <AssistantHeader model={model} pending={pending} notice={notice} archiveOpen={archiveOpen} setArchiveOpen={setArchiveOpen} onDuplicate={duplicate} onArchive={archive} />
      <AssistantTabs selected={selected} assistantId={model.assistantId} />

      <motion.div
        className="assistantDetailContent"
        key={selected}
        initial={reduceMotion ? false : { opacity: 0, y: 12 }}
        animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
      >
        {selected === "overview" ? <OverviewTab model={model} /> : null}
        {selected === "knowledge" ? <KnowledgeTab model={model} /> : null}
        {selected === "playground" ? <PlaygroundTab session={props.session} assistantId={model.assistantId} /> : null}
        {selected === "widget" ? <WidgetDetailClient session={props.session} initialWidget={props.initialWidget} initialDraft={props.initialDraft} initialOrigins={props.initialOrigins} initialEmbed={props.initialEmbed} sdkVersions={props.initialSdkVersions} knowledgeOptions={props.initialKnowledgeOptions} initialRevisions={props.initialRevisions} initialInstallationStatus={props.initialInstallationStatus} /> : null}
        {selected === "analytics" ? <AnalyticsTab model={model} /> : null}
        {selected === "settings" ? <SettingsTab model={model} pending={pending} onDuplicate={duplicate} onArchive={() => setArchiveOpen(true)} /> : null}
      </motion.div>
    </section>
  );
}

function AssistantHeader({ model, pending, notice, archiveOpen, setArchiveOpen, onDuplicate, onArchive }: { model: DetailModel; pending: PendingAction; notice: string | null; archiveOpen: boolean; setArchiveOpen: (open: boolean) => void; onDuplicate: () => void; onArchive: () => void }) {
  const reduceMotion = useReducedMotion();
  const PrimaryIcon = model.nextAction.icon;
  return (
    <motion.header
      className={`premiumAssistantDetailHeader${model.lifecycle === "Archived" ? " premiumAssistantDetailArchived" : ""}`}
      initial={reduceMotion ? false : { opacity: 0, y: 16 }}
      animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="assistantDetailHeaderMain">
        <div className="assistantDetailAvatar" aria-hidden="true"><Bot size={28} /></div>
        <div>
          <p className="assistantEyebrow">Assistant Control Centre</p>
          <h2 id="assistant-detail-title">{model.widget.display_name}</h2>
          <p>{model.description}</p>
          <div className="assistantDetailMetaLine" aria-label="Assistant state summary">
            <AssistantStatusBadge status={model.lifecycle} />
            <span><Clock3 size={14} aria-hidden="true" />Updated {formatDateTime(model.widget.updated_at)}</span>
            <span><ShieldCheck size={14} aria-hidden="true" />Assistant scoped</span>
          </div>
        </div>
      </div>
      <div className="assistantDetailHeaderActions">
        <Link className="assistantPrimaryCta" href={model.nextAction.href} aria-label={`${model.nextAction.label}: ${model.nextAction.helper}`}>
          <PrimaryIcon size={17} aria-hidden="true" />
          {model.nextAction.label}
        </Link>
        <details className="assistantDetailOverflow">
          <summary role="button" tabIndex={0} aria-haspopup="menu" aria-label={`More actions for ${model.widget.display_name}`}><MoreHorizontal size={18} aria-hidden="true" /></summary>
          <div className="assistantDetailOverflowMenu" role="menu">
            <button type="button" role="menuitem" onClick={onDuplicate} disabled={pending !== null} aria-label={`Duplicate ${model.widget.display_name}`}>
              {pending === "duplicate" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : <Copy size={15} aria-hidden="true" />}
              {pending === "duplicate" ? "Duplicating" : "Duplicate"}
            </button>
            <button type="button" role="menuitem" onClick={() => setArchiveOpen(true)} disabled={pending !== null} aria-label={`Archive ${model.widget.display_name}`}>
              <Archive size={15} aria-hidden="true" />Archive
            </button>
          </div>
        </details>
      </div>
      {notice ? <p className="assistantDetailNotice" role="alert">{notice}</p> : null}
      <ArchiveDialog open={archiveOpen} name={model.widget.display_name} pending={pending === "archive"} onCancel={() => setArchiveOpen(false)} onConfirm={onArchive} />
    </motion.header>
  );
}

function AssistantTabs({ selected, assistantId }: { selected: AssistantTab; assistantId: string }) {
  const reduceMotion = useReducedMotion();
  return (
    <nav className="premiumAssistantTabs" aria-label="Assistant sections">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = selected === tab.id;
        return (
          <Link key={tab.id} className={`premiumAssistantTab${active ? " active" : ""}`} href={tabHref(assistantId, tab.id)} aria-current={active ? "page" : undefined}>
            <Icon size={16} aria-hidden="true" />
            {tab.label}
            {active ? <motion.span className="assistantTabIndicator" layoutId="assistant-tab-indicator" transition={reduceMotion ? { duration: 0 } : { duration: 0.2 }} /> : null}
          </Link>
        );
      })}
    </nav>
  );
}

function OverviewTab({ model }: { model: DetailModel }) {
  return (
    <div className="premiumAssistantOverviewGrid">
      <section className="assistantExecutivePanel" aria-labelledby="assistant-executive-title">
        <div className="assistantPanelHeading">
          <p className="assistantEyebrow">Executive Summary</p>
          <h3 id="assistant-executive-title">Operating posture</h3>
          <p>Current state is calculated from loaded assistant, knowledge, widget, conversation, and review data.</p>
        </div>
        <div className="assistantSummaryCards">
          <AssistantSummaryCard icon={Bot} label="Lifecycle" value={model.lifecycle} helper={model.nextAction.helper} />
          <AssistantSummaryCard icon={Database} label="Knowledge sources" value={model.knowledgeCounts.total.toString()} helper={`${model.knowledgeCounts.ready} ready, ${model.knowledgeCounts.processing} processing, ${model.knowledgeCounts.failed} failed`} />
          <AssistantSummaryCard icon={MessageSquare} label="Conversations" value={model.conversations.length.toString()} helper="Assistant-scoped recent window" />
          <AssistantSummaryCard icon={Rocket} label="Widget" value={model.embed.published ? "Published" : "Draft"} helper={model.embed.active ? "Embed readiness passed" : "Not live yet"} />
        </div>
        <AssistantQuickActions assistantId={model.assistantId} />
      </section>

      <aside className="assistantDetailSidePanel" aria-label="Assistant setup and activity">
        <SetupChecklist items={model.setupItems} />
        <AssistantActivityFeed items={model.recentActivity} />
      </aside>

      <KnowledgeSnapshot model={model} />
      <ConversationSnapshot model={model} />
      <WidgetSnapshot model={model} />
      <AnalyticsSnapshot model={model} />
    </div>
  );
}

function AssistantSummaryCard({ icon: Icon, label, value, helper }: { icon: LucideIcon; label: string; value: string; helper: string }) {
  return (
    <article className="assistantSummaryCard">
      <span aria-hidden="true"><Icon size={18} /></span>
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{helper}</small>
    </article>
  );
}

function SetupChecklist({ items }: { items: DetailModel["setupItems"] }) {
  const complete = items.filter((item) => item.complete).length;
  const percent = Math.round((complete / items.length) * 100);
  return (
    <section className="assistantSetupPanel" aria-labelledby="assistant-setup-title">
      <div className="assistantPanelHeaderInline">
        <div>
          <h3 id="assistant-setup-title">Setup progress</h3>
          <p>{complete} of {items.length} complete</p>
        </div>
        <strong>{percent}%</strong>
      </div>
      <div className="assistantProgressTrack" aria-label={`Setup progress ${percent}%`}><span style={{ width: `${percent}%` }} /></div>
      <ol className="assistantSetupList">
        {items.map((item) => <li key={item.label} data-complete={item.complete}><span aria-hidden="true">{item.complete ? <CheckCircle2 size={16} /> : <CircleDashed size={16} />}</span><div><strong>{item.label}</strong><p>{item.helper}</p></div></li>)}
      </ol>
    </section>
  );
}

function AssistantQuickActions({ assistantId }: { assistantId: string }) {
  const actions = [
    { label: "Add knowledge", href: `/knowledge?assistant=${assistantId}`, icon: Plus },
    { label: "Test assistant", href: tabHref(assistantId, "playground"), icon: MessageSquare },
    { label: "Configure widget", href: tabHref(assistantId, "widget"), icon: Rocket },
    { label: "View analytics", href: tabHref(assistantId, "analytics"), icon: BarChart3 },
    { label: "Open conversations", href: `/conversations?assistant=${assistantId}`, icon: Activity },
    { label: "Edit settings", href: tabHref(assistantId, "settings"), icon: Settings },
  ];
  return (
    <section className="assistantQuickActions" aria-label="Assistant quick actions">
      {actions.map((action) => <Link key={action.label} href={action.href}><action.icon size={16} aria-hidden="true" />{action.label}<ChevronRight size={14} aria-hidden="true" /></Link>)}
    </section>
  );
}

function AssistantActivityFeed({ items }: { items: DetailModel["recentActivity"] }) {
  return (
    <section className="assistantActivityPanel" aria-labelledby="assistant-activity-title">
      <h3 id="assistant-activity-title">Recent activity</h3>
      <p>Derived from loaded assistant revisions, assigned knowledge, conversations, and review signals.</p>
      {items.length === 0 ? <div className="assistantEmptyInline"><Sparkles size={16} aria-hidden="true" />No recent assistant-scoped activity yet.</div> : (
        <ul>
          {items.map((item, index) => <li key={`${item.label}-${index}`}><span aria-hidden="true"><item.icon size={15} /></span><div><strong>{item.label}</strong><p>{item.helper}</p><small>{item.time ? formatDateTime(item.time) : "No timestamp"}</small></div></li>)}
        </ul>
      )}
    </section>
  );
}

function KnowledgeSnapshot({ model }: { model: DetailModel }) {
  return (
    <section className="assistantSnapshotPanel" aria-labelledby="knowledge-snapshot-title">
      <div className="assistantPanelHeaderInline"><div><h3 id="knowledge-snapshot-title">Knowledge snapshot</h3><p>Assigned documents and readiness for this assistant.</p></div><Link href={tabHref(model.assistantId, "knowledge")}>Full Knowledge tab</Link></div>
      <dl className="assistantSnapshotStats"><div><dt>Total</dt><dd>{model.knowledgeCounts.total}</dd></div><div><dt>Ready</dt><dd>{model.knowledgeCounts.ready}</dd></div><div><dt>Processing</dt><dd>{model.knowledgeCounts.processing}</dd></div><div><dt>Failed</dt><dd>{model.knowledgeCounts.failed}</dd></div></dl>
      {model.scopedKnowledge.length === 0 ? <div className="assistantEmptyInline"><FileText size={16} aria-hidden="true" />No knowledge sources are assigned yet.</div> : <ul className="assistantCompactList">{model.scopedKnowledge.slice(0, 4).map((item) => <li key={item.id}><strong>{item.title}</strong><span>{item.type} - {item.readiness}</span></li>)}</ul>}
    </section>
  );
}

function ConversationSnapshot({ model }: { model: DetailModel }) {
  return (
    <section className="assistantSnapshotPanel" aria-labelledby="conversation-snapshot-title">
      <div className="assistantPanelHeaderInline"><div><h3 id="conversation-snapshot-title">Conversation snapshot</h3><p>Recent assistant-scoped conversation window.</p></div><Link href={`/conversations?assistant=${model.assistantId}`}>Open Conversations</Link></div>
      <dl className="assistantSnapshotStats"><div><dt>Recent</dt><dd>{model.conversations.length}</dd></div><div><dt>Fallback or low confidence</dt><dd>{model.fallbackOrLowConfidence}</dd></div></dl>
      {model.conversations.length === 0 ? <div className="assistantEmptyInline"><MessageSquare size={16} aria-hidden="true" />No conversations recorded for this assistant yet.</div> : <ul className="assistantCompactList">{model.conversations.slice(0, 4).map((conversation) => <li key={conversation.id}><strong>{conversation.title || "Untitled conversation"}</strong><span>{conversation.channel} - {formatDateTime(conversation.last_message_at || conversation.started_at)}</span></li>)}</ul>}
    </section>
  );
}

function WidgetSnapshot({ model }: { model: DetailModel }) {
  return (
    <section className="assistantSnapshotPanel" aria-labelledby="widget-snapshot-title">
      <div className="assistantPanelHeaderInline"><div><h3 id="widget-snapshot-title">Widget snapshot</h3><p>Publication, credential, origin, and embed readiness.</p></div><Link href={tabHref(model.assistantId, "widget")}>Configure Widget</Link></div>
      <div className="assistantWidgetPreview" aria-label="Widget preview thumbnail"><div><Bot size={18} aria-hidden="true" /><strong>{model.draft.configuration.bot_name}</strong></div><p>{model.draft.configuration.welcome_message}</p><button type="button">{model.draft.configuration.launcher_label}</button></div>
      <dl className="assistantSnapshotStats"><div><dt>Publication</dt><dd>{model.embed.published ? "Published" : "Draft"}</dd></div><div><dt>Credential</dt><dd>{model.embed.public_key_status}</dd></div><div><dt>Origins</dt><dd>{model.origins.filter((origin) => origin.active).length}</dd></div><div><dt>Readiness</dt><dd>{model.embed.readiness.join(", ") || "ready"}</dd></div></dl>
    </section>
  );
}

function AnalyticsSnapshot({ model }: { model: DetailModel }) {
  return (
    <section className="assistantSnapshotPanel" aria-labelledby="analytics-snapshot-title">
      <div className="assistantPanelHeaderInline"><div><h3 id="analytics-snapshot-title">Analytics snapshot</h3><p>Partial metrics from sampled assistant-scoped windows.</p></div><Link href={tabHref(model.assistantId, "analytics")}>Full Analytics tab</Link></div>
      <dl className="assistantSnapshotStats"><div><dt>Sampled conversations</dt><dd>{model.conversations.length}</dd></div><div><dt>Citation coverage</dt><dd>{model.citationCoverage === null ? "N/A" : `${model.citationCoverage}%`}</dd></div><div><dt>Fallback rate</dt><dd>{model.conversations.length === 0 ? "N/A" : `${Math.round((model.fallbackOrLowConfidence / model.conversations.length) * 100)}%`}</dd></div><div><dt>Avg latency</dt><dd>{model.averageLatency === null ? "N/A" : `${model.averageLatency}ms`}</dd></div><div><dt>Knowledge gaps</dt><dd>{model.reviewItems.length}</dd></div><div><dt>Publication</dt><dd>{model.embed.published ? "Published" : "Draft"}</dd></div></dl>
    </section>
  );
}

function KnowledgeTab({ model }: { model: DetailModel }) {
  return (
    <section className="assistantDetailPanel premiumAssistantTabPanel wide">
      <div className="assistantPanelHeaderInline">
        <div><h3>Knowledge</h3><p>{model.scopedKnowledge.length} approved documents are scoped to this assistant.</p></div>
        <Link className="assistantAction primary" href={`/knowledge?assistant=${model.assistantId}`}>Add Knowledge</Link>
      </div>
      {model.scopedKnowledge.length === 0 ? <p className="assistantMuted">No documents are scoped yet. Add sources from Knowledge Base or configure the widget knowledge scope.</p> : (
        <div className="assistantKnowledgeList">{model.scopedKnowledge.map((item) => <article key={item.id}><strong>{item.title}</strong><span>{item.type} - {item.readiness}</span></article>)}</div>
      )}
    </section>
  );
}

function PlaygroundTab({ session, assistantId }: { session: DevelopmentDashboardSession; assistantId: string }) {
  return <div className="assistantPlaygroundShell"><ChatbotClient session={session} assistantId={assistantId} /></div>;
}

function AnalyticsTab({ model }: { model: DetailModel }) {
  return <div className="assistantDetailGrid premiumAssistantAnalyticsGrid"><AnalyticsSnapshot model={model} /><ConversationSnapshot model={model} /></div>;
}

function SettingsTab({ model, pending, onDuplicate, onArchive }: { model: DetailModel; pending: PendingAction; onDuplicate: () => void; onArchive: () => void }) {
  return (
    <section className="assistantDetailPanel premiumAssistantTabPanel wide">
      <h3>Lifecycle Settings</h3>
      <p>Duplicate this assistant to create a new draft from the current configuration, or archive it when it should no longer appear in active workspace views.</p>
      <div className="assistantSettingsActions">
        <button className="assistantAction" type="button" onClick={onDuplicate} disabled={pending !== null}>{pending === "duplicate" ? "Duplicating Assistant" : "Duplicate Assistant"}</button>
        <button className="assistantAction danger" type="button" onClick={onArchive} disabled={pending !== null}><Archive size={15} aria-hidden="true" />Archive Assistant</button>
      </div>
      <p className="assistantMuted">Assistant ID remains internal and is only used in routing context.</p>
      <code>{model.widget.public_identifier}</code>
    </section>
  );
}

function ArchiveDialog({ open, name, pending, onCancel, onConfirm }: { open: boolean; name: string; pending: boolean; onCancel: () => void; onConfirm: () => void }) {
  const reduceMotion = useReducedMotion();
  return (
    <AnimatePresence>
      {open ? (
        <motion.div className="assistantDialogBackdrop" initial={reduceMotion ? false : { opacity: 0 }} animate={reduceMotion ? undefined : { opacity: 1 }} exit={reduceMotion ? undefined : { opacity: 0 }}>
          <motion.div className="assistantConfirmDialog" role="dialog" aria-modal="true" aria-labelledby="archive-assistant-title" initial={reduceMotion ? false : { opacity: 0, y: 18, scale: 0.98 }} animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }} exit={reduceMotion ? undefined : { opacity: 0, y: 12, scale: 0.98 }}>
            <div className="assistantConfirmIcon" aria-hidden="true"><Archive size={22} /></div>
            <h3 id="archive-assistant-title">Archive assistant?</h3>
            <p>{name} will be removed from active assistant management. Existing archive behavior is preserved.</p>
            <div className="assistantConfirmActions"><button type="button" className="assistantAction" onClick={onCancel} disabled={pending}>Cancel</button><button type="button" className="assistantAction danger solid" onClick={onConfirm} disabled={pending}>{pending ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : <Archive size={15} aria-hidden="true" />}{pending ? "Archiving" : "Archive"}</button></div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export function AssistantDetailSkeleton() {
  return <section className="premiumAssistantDetailPage" aria-label="Loading assistant detail"><div className="premiumAssistantDetailHeader assistantSkeletonBlock" /><div className="premiumAssistantTabs assistantSkeletonBlock" /><div className="premiumAssistantOverviewGrid"><div className="assistantExecutivePanel assistantSkeletonBlock" /><div className="assistantDetailSidePanel assistantSkeletonBlock" /><div className="assistantSnapshotPanel assistantSkeletonBlock" /><div className="assistantSnapshotPanel assistantSkeletonBlock" /></div></section>;
}

export function AssistantDetailErrorState({ title = "Assistant unavailable", message, retryHref = "/dashboard" }: { title?: string; message: string; retryHref?: string }) {
  return <section className="assistantDashboardError" role="alert" aria-labelledby="assistant-detail-error-title"><AlertCircle size={28} aria-hidden="true" /><p className="assistantEyebrow">Assistant detail</p><h2 id="assistant-detail-error-title">{title}</h2><p>{message}</p><Link className="assistantPrimaryCta" href={retryHref}>Retry</Link></section>;
}

function buildDetailModel(props: AssistantDetailClientProps): DetailModel {
  const assistantId = props.initialWidget.id;
  const lifecycle = assistantLifecycle(props.initialWidget);
  const selectedIds = new Set(props.initialDraft.configuration.knowledge_scope_json);
  const scopedKnowledge = props.initialKnowledgeOptions.filter((option) => selectedIds.has(option.id));
  const conversations = assistantConversations(props.overviewData, props.initialWidget);
  const reviewItems = props.overviewData.reviewItems.filter((item) => item.assistant_id === assistantId || conversations.some((conversation) => conversation.id === item.conversation_id));
  const fallbackOrLowConfidence = reviewItems.filter((item) => item.answer_state === "fallback" || item.answer_state === "low_confidence").length;
  const latencyValues = reviewItems.map((item) => item.latency_ms).filter((value): value is number => typeof value === "number");
  const citationCoverage = reviewItems.length === 0 ? null : Math.round((reviewItems.filter((item) => item.citation_count > 0).length / reviewItems.length) * 100);
  const knowledgeCounts = {
    total: scopedKnowledge.length,
    ready: scopedKnowledge.filter((item) => item.readiness === "ready" || item.indexing_status === "ready").length,
    processing: scopedKnowledge.filter((item) => ["indexing", "processing", "pending", "uploaded"].includes(item.readiness) || ["processing", "pending", "uploaded"].includes(item.indexing_status)).length,
    failed: scopedKnowledge.filter((item) => item.readiness === "failed" || item.indexing_status === "failed" || item.indexing_status === "error").length,
  };
  const setupItems = [
    { label: "Assistant created", complete: true, helper: `Created ${formatDateTime(props.initialWidget.created_at)}` },
    { label: "Knowledge uploaded", complete: knowledgeCounts.total > 0, helper: knowledgeCounts.total > 0 ? `${knowledgeCounts.total} assigned source${knowledgeCounts.total === 1 ? "" : "s"}` : "Add approved knowledge" },
    { label: "Knowledge processed", complete: knowledgeCounts.total > 0 && knowledgeCounts.ready === knowledgeCounts.total, helper: knowledgeCounts.total === 0 ? "No assigned sources" : `${knowledgeCounts.ready} ready` },
    { label: "Playground tested", complete: conversations.some((conversation) => conversation.channel === "dashboard_test"), helper: "Based on dashboard test conversations" },
    { label: "Widget configured", complete: props.initialOrigins.some((origin) => origin.active), helper: props.initialOrigins.some((origin) => origin.active) ? "Allowed origin configured" : "Add an allowed origin" },
    { label: "Published", complete: props.initialEmbed.published, helper: props.initialEmbed.published ? "Published revision available" : "Publish when ready" },
  ];
  const nextAction = primaryAction({ assistantId, lifecycle, knowledgeCounts, embed: props.initialEmbed, conversations });
  const recentActivity = buildRecentActivity({ scopedKnowledge, conversations, reviewItems, revisions: props.initialRevisions, widget: props.initialWidget });
  return {
    widget: props.initialWidget,
    draft: props.initialDraft,
    embed: props.initialEmbed,
    origins: props.initialOrigins,
    installationStatus: props.initialInstallationStatus,
    knowledgeOptions: props.initialKnowledgeOptions,
    revisions: props.initialRevisions,
    overviewData: props.overviewData,
    assistantId,
    lifecycle,
    description: props.initialDraft.configuration.welcome_message || "Source-grounded assistant configured for this workspace.",
    scopedKnowledge,
    knowledgeCounts,
    conversations,
    reviewItems,
    fallbackOrLowConfidence,
    averageLatency: latencyValues.length === 0 ? null : Math.round(latencyValues.reduce((sum, value) => sum + value, 0) / latencyValues.length),
    citationCoverage,
    setupItems,
    nextAction,
    recentActivity,
  };
}

function primaryAction(input: { assistantId: string; lifecycle: ReturnType<typeof assistantLifecycle>; knowledgeCounts: DetailModel["knowledgeCounts"]; embed: WidgetEmbedMetadata; conversations: OverviewData["conversations"] }) {
  if (input.embed.active) return { label: "View live widget", href: tabHref(input.assistantId, "widget"), icon: Globe2, helper: "Widget is published and active" };
  if (input.knowledgeCounts.total === 0) return { label: "Continue setup", href: `/knowledge?assistant=${input.assistantId}`, icon: Plus, helper: "Add knowledge before publishing" };
  if (input.lifecycle === "Ready" || input.lifecycle === "Published") return { label: "Test", href: tabHref(input.assistantId, "playground"), icon: MessageSquare, helper: "Open the authenticated playground" };
  if (input.conversations.length > 0) return { label: "Publish", href: tabHref(input.assistantId, "widget"), icon: Rocket, helper: "Review widget readiness and publish" };
  return { label: "Test", href: tabHref(input.assistantId, "playground"), icon: MessageSquare, helper: "Validate responses before publishing" };
}

function buildRecentActivity(input: { scopedKnowledge: WidgetKnowledgeOption[]; conversations: OverviewData["conversations"]; reviewItems: OverviewData["reviewItems"]; revisions: WidgetRevisionDetail[]; widget: WidgetDetail }) {
  const items = [
    ...input.scopedKnowledge.slice(0, 3).map((item) => ({ icon: FileText, label: item.title, helper: `Knowledge ${item.readiness}`, time: item.updated_at })),
    ...input.conversations.slice(0, 3).map((item) => ({ icon: MessageSquare, label: item.title || "Conversation", helper: `${item.channel} - ${item.status}`, time: item.last_message_at || item.started_at })),
    ...input.reviewItems.slice(0, 2).map((item) => ({ icon: AlertCircle, label: "Review item", helper: `${item.answer_state} - ${item.review_status}`, time: item.created_at })),
    ...input.revisions.slice(0, 2).map((item) => ({ icon: Rocket, label: `Revision ${item.revision_number}`, helper: item.status, time: item.published_at || item.created_at })),
    { icon: Bot, label: "Assistant updated", helper: input.widget.operational_status, time: input.widget.updated_at },
  ];
  return items.sort((a, b) => new Date(b.time || 0).getTime() - new Date(a.time || 0).getTime()).slice(0, 6);
}

function assistantConversations(data: OverviewData, assistant: WidgetDetail) {
  return data.conversations.filter((conversation) => {
    const metadata = conversation.metadata ?? {};
    return conversation.assistant_id === assistant.id || metadata.widget_id === assistant.id || metadata.assistant_id === assistant.id || metadata.public_identifier === assistant.public_identifier;
  });
}

function tabHref(assistantId: string, tab: AssistantTab) {
  return `/assistants/${assistantId}?tab=${tab}&assistant=${assistantId}`;
}

function withAssistantContext(path: string, assistantId: string) {
  return `${path}${path.includes("?") ? "&" : "?"}assistant=${assistantId}`;
}

function coerceTab(value: string | null): AssistantTab {
  return tabs.some((tab) => tab.id === value) ? value as AssistantTab : "overview";
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}
