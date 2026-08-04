"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Archive,
  BarChart3,
  Bot,
  CheckCircle2,
  Clock3,
  Copy,
  ExternalLink,
  FileText,
  Grid3X3,
  List,
  Loader2,
  MoreHorizontal,
  Pencil,
  Plus,
  Rocket,
  Search,
  SlidersHorizontal,
  Sparkles,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { isDashboardApiError } from "../../lib/api/errors";
import type { OverviewData } from "../../lib/api/overview";
import { archiveWidget, duplicateWidget, type WidgetDetail, type WidgetSummary } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type AssistantManagementProps = {
  session: DevelopmentDashboardSession;
  assistants: WidgetDetail[];
  data: OverviewData;
};

type AssistantStatus = "Draft" | "Training" | "Ready" | "Published" | "Archived";
type StatusFilter = "all" | AssistantStatus;
type SortOption = "updated-desc" | "updated-asc" | "name-asc" | "name-desc" | "status-asc";
type ViewMode = "grid" | "list";

type AssistantCardModel = WidgetDetail & {
  lifecycle: AssistantStatus;
  knowledgeCount: number;
  conversationCount: number;
  description: string;
};

type PendingAction = { id: string; action: "duplicate" | "archive" } | null;

const statusFilters: StatusFilter[] = ["all", "Draft", "Training", "Ready", "Published", "Archived"];
const lifecycleOrder: Record<AssistantStatus, number> = { Published: 0, Ready: 1, Training: 2, Draft: 3, Archived: 4 };

const lifecycleMeta: Record<AssistantStatus, { icon: LucideIcon; description: string }> = {
  Published: { icon: Rocket, description: "Published and available to customers" },
  Ready: { icon: CheckCircle2, description: "Ready to publish or test" },
  Training: { icon: Loader2, description: "Training is in progress" },
  Draft: { icon: Pencil, description: "Draft changes need review" },
  Archived: { icon: Archive, description: "Archived and hidden from active work" },
};

export function AssistantManagement({ session, assistants, data }: AssistantManagementProps) {
  const reduceMotion = useReducedMotion();
  const [items, setItems] = useState<WidgetDetail[]>(assistants);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [sort, setSort] = useState<SortOption>("updated-desc");
  const [view, setView] = useState<ViewMode>("grid");
  const [pending, setPending] = useState<PendingAction>(null);
  const [archiveTarget, setArchiveTarget] = useState<AssistantCardModel | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "danger"; message: string } | null>(null);

  const selectedAssistantId = getSelectedAssistantId(session.workspaceId);
  const cards = useMemo(() => buildAssistantCards(items, data), [items, data]);
  const metrics = useMemo(() => buildAssistantMetrics(cards), [cards]);
  const filtered = useMemo(() => filterAndSortAssistants(cards, query, status, sort), [cards, query, sort, status]);

  async function onDuplicate(assistant: AssistantCardModel) {
    setPending({ id: assistant.id, action: "duplicate" });
    setNotice(null);
    try {
      const response = await duplicateWidget(session, assistant.id);
      setItems((current) => [response.data, ...current]);
      setNotice({ tone: "success", message: `${assistant.display_name} was duplicated.` });
    } catch (caught) {
      setNotice({ tone: "danger", message: messageForAssistantError(caught, "Assistant could not be duplicated.") });
    } finally {
      setPending(null);
    }
  }

  async function confirmArchive() {
    if (!archiveTarget) return;
    setPending({ id: archiveTarget.id, action: "archive" });
    setNotice(null);
    try {
      await archiveWidget(session, archiveTarget.id);
      setItems((current) => current.filter((item) => item.id !== archiveTarget.id));
      setNotice({ tone: "success", message: `${archiveTarget.display_name} was archived.` });
      setArchiveTarget(null);
    } catch (caught) {
      setNotice({ tone: "danger", message: messageForAssistantError(caught, "Assistant could not be archived.") });
    } finally {
      setPending(null);
    }
  }

  if (items.length === 0) {
    return <AssistantEmptyState />;
  }

  return (
    <section className="assistantPage assistantDashboardPage" aria-labelledby="assistants-title">
      <motion.div
        className="assistantDashboardHeader"
        initial={reduceMotion ? false : { opacity: 0, y: 18 }}
        animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
      >
        <div>
          <p className="assistantEyebrow">Workspace assistants</p>
          <h2 id="assistants-title">My AI Assistants</h2>
          <p>Build, manage, publish, and monitor every Conversa assistant in {session.workspaceName} without leaving your workspace context.</p>
        </div>
        <Link className="assistantPrimaryCta assistantHeaderCta" href="/assistants/new">
          <Plus size={18} aria-hidden="true" />
          Create Assistant
        </Link>
      </motion.div>

      <AssistantMetrics metrics={metrics} />

      <AssistantFilters query={query} status={status} sort={sort} view={view} resultCount={filtered.length} onQueryChange={setQuery} onStatusChange={setStatus} onSortChange={setSort} onViewChange={setView} />

      <AnimatePresence>
        {notice ? (
          <motion.div
            className={`assistantFeedback assistantFeedback${notice.tone === "success" ? "Success" : "Danger"}`}
            role="status"
            initial={reduceMotion ? false : { opacity: 0, y: -6 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: -6 }}
          >
            {notice.tone === "success" ? <CheckCircle2 size={17} aria-hidden="true" /> : <XCircle size={17} aria-hidden="true" />}
            <span>{notice.message}</span>
            <button type="button" aria-label="Dismiss notification" onClick={() => setNotice(null)}>Dismiss</button>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {filtered.length === 0 ? (
        <AssistantNoResults />
      ) : (
        <motion.div className={`assistantCollection assistantCollection${view === "list" ? "List" : "Grid"}`} initial={false} layout>
          {filtered.map((assistant, index) => (
            <AssistantCard
              key={assistant.id}
              assistant={assistant}
              index={index}
              reducedMotion={Boolean(reduceMotion)}
              selected={selectedAssistantId === assistant.id}
              pending={pending?.id === assistant.id ? pending.action : null}
              view={view}
              onDuplicate={onDuplicate}
              onArchive={() => setArchiveTarget(assistant)}
            />
          ))}
        </motion.div>
      )}

      <ArchiveAssistantDialog target={archiveTarget} pending={Boolean(pending && archiveTarget && pending.id === archiveTarget.id && pending.action === "archive")} onCancel={() => setArchiveTarget(null)} onConfirm={confirmArchive} />
    </section>
  );
}

function AssistantMetrics({ metrics }: { metrics: ReturnType<typeof buildAssistantMetrics> }) {
  const reduceMotion = useReducedMotion();
  return (
    <section className="assistantMetrics" aria-label="Assistant summary metrics">
      {metrics.map((metric, index) => {
        const Icon = metric.icon;
        return (
          <motion.article
            className="assistantMetricCard"
            key={metric.label}
            initial={reduceMotion ? false : { opacity: 0, y: 14 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
            transition={{ duration: 0.26, delay: Math.min(index * 0.05, 0.2) }}
            whileHover={reduceMotion ? undefined : { y: -2 }}
          >
            <span className="assistantMetricIcon" aria-hidden="true"><Icon size={18} /></span>
            <div>
              <p>{metric.label}</p>
              <strong aria-label={`${metric.label}: ${metric.value}`}>{metric.value}</strong>
              <span>{metric.helper}</span>
            </div>
          </motion.article>
        );
      })}
    </section>
  );
}

function AssistantFilters(props: {
  query: string;
  status: StatusFilter;
  sort: SortOption;
  view: ViewMode;
  resultCount: number;
  onQueryChange: (value: string) => void;
  onStatusChange: (value: StatusFilter) => void;
  onSortChange: (value: SortOption) => void;
  onViewChange: (value: ViewMode) => void;
}) {
  return (
    <section className="assistantControlSurface" aria-label="Assistant search, filters, and view controls">
      <div className="assistantControlSummary">
        <p>Assistants</p>
        <span>{props.resultCount} shown. Filters run locally on the loaded workspace assistant list.</span>
      </div>
      <div className="assistantControlBar premiumAssistantControlBar">
        <label className="assistantSearch premiumAssistantSearch">
          <Search size={17} aria-hidden="true" />
          <span className="srOnly">Search assistants by name or description</span>
          <input value={props.query} onChange={(event) => props.onQueryChange(event.target.value)} placeholder="Search assistants" />
        </label>
        <label className="assistantSelect premiumAssistantSelect">
          <SlidersHorizontal size={17} aria-hidden="true" />
          <span className="srOnly">Filter assistants by status</span>
          <select value={props.status} onChange={(event) => props.onStatusChange(event.target.value as StatusFilter)}>
            {statusFilters.map((option) => <option key={option} value={option}>{option === "all" ? "All statuses" : option}</option>)}
          </select>
        </label>
        <label className="assistantSelect premiumAssistantSelect">
          <Clock3 size={17} aria-hidden="true" />
          <span className="srOnly">Sort assistants</span>
          <select value={props.sort} onChange={(event) => props.onSortChange(event.target.value as SortOption)}>
            <option value="updated-desc">Newest updated</option>
            <option value="updated-asc">Oldest updated</option>
            <option value="name-asc">Name A-Z</option>
            <option value="name-desc">Name Z-A</option>
            <option value="status-asc">Status priority</option>
          </select>
        </label>
        <div className="assistantViewToggle" role="group" aria-label="Assistant view mode">
          <button type="button" aria-pressed={props.view === "grid"} onClick={() => props.onViewChange("grid")}><Grid3X3 size={16} aria-hidden="true" />Grid</button>
          <button type="button" aria-pressed={props.view === "list"} onClick={() => props.onViewChange("list")}><List size={16} aria-hidden="true" />List</button>
        </div>
      </div>
    </section>
  );
}

function AssistantCard(props: {
  assistant: AssistantCardModel;
  index: number;
  reducedMotion: boolean;
  selected: boolean;
  pending: "duplicate" | "archive" | null;
  view: ViewMode;
  onDuplicate: (assistant: AssistantCardModel) => void;
  onArchive: () => void;
}) {
  const { assistant, pending } = props;
  const IdentityIcon = lifecycleMeta[assistant.lifecycle].icon;
  const disabled = Boolean(pending);
  return (
    <motion.article
      className={`premiumAssistantCard ${props.view === "list" ? "premiumAssistantCardList" : ""}${props.selected ? " premiumAssistantCardSelected" : ""}`}
      aria-labelledby={`assistant-${assistant.id}-title`}
      initial={props.reducedMotion ? false : { opacity: 0, y: 16 }}
      animate={props.reducedMotion ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: Math.min(props.index * 0.04, 0.18) }}
      whileHover={props.reducedMotion ? undefined : { y: -3 }}
      layout
    >
      <div className="assistantCardTopline">
        <div className="assistantAvatar" aria-hidden="true"><IdentityIcon size={22} /></div>
        <div className="assistantTitleBlock">
          <div className="assistantTitleRow">
            <h3 id={`assistant-${assistant.id}-title`}>{assistant.display_name}</h3>
            {props.selected ? <span className="assistantCurrentPill"><Sparkles size={13} aria-hidden="true" />Current</span> : null}
          </div>
          <p>{assistant.description}</p>
        </div>
        <AssistantStatusBadge status={assistant.lifecycle} />
      </div>

      <div className="assistantLifecycleLine">
        <span aria-hidden="true" />
        <strong>{assistant.lifecycle}</strong>
        <p>{lifecycleMeta[assistant.lifecycle].description}</p>
      </div>

      <dl className="premiumAssistantFacts">
        <div><dt>Knowledge</dt><dd><FileText size={15} aria-hidden="true" />{assistant.knowledgeCount}</dd></div>
        <div><dt>Widget</dt><dd>{widgetStatusLabel(assistant)}</dd></div>
        <div><dt>Conversations</dt><dd>{assistant.conversationCount}</dd></div>
        <div><dt>Updated</dt><dd>{formatShortDate(assistant.updated_at)}</dd></div>
      </dl>

      <div className="assistantPrimaryRow">
        <Link className="assistantAction primary" href={`/assistants/${assistant.id}?assistant=${assistant.id}`}><ExternalLink size={15} aria-hidden="true" />Open</Link>
        <Link className="assistantAction" href={`/assistants/${assistant.id}?tab=settings&assistant=${assistant.id}`}><Pencil size={15} aria-hidden="true" />Edit</Link>
        <Link className="assistantAction" href={`/assistants/${assistant.id}?tab=analytics&assistant=${assistant.id}`}><BarChart3 size={15} aria-hidden="true" />Analytics</Link>
        <Link className="assistantAction" href={`/assistants/${assistant.id}?tab=widget&assistant=${assistant.id}`}><Rocket size={15} aria-hidden="true" />Publish</Link>
        <details className="assistantOverflow">
          <summary role="button" tabIndex={0} aria-haspopup="menu" aria-label={`More actions for ${assistant.display_name}`}><MoreHorizontal size={17} aria-hidden="true" /></summary>
          <div className="assistantOverflowMenu" role="menu">
            <button type="button" role="menuitem" onClick={() => props.onDuplicate(assistant)} disabled={disabled} aria-label={`Duplicate ${assistant.display_name}`}>
              {pending === "duplicate" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : <Copy size={15} aria-hidden="true" />}
              {pending === "duplicate" ? "Duplicating" : "Duplicate"}
            </button>
            <button type="button" role="menuitem" onClick={props.onArchive} disabled={disabled} aria-label={`Archive ${assistant.display_name}`}>
              {pending === "archive" ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : <Archive size={15} aria-hidden="true" />}
              {pending === "archive" ? "Archiving" : "Archive"}
            </button>
          </div>
        </details>
      </div>
    </motion.article>
  );
}

function ArchiveAssistantDialog({ target, pending, onCancel, onConfirm }: { target: AssistantCardModel | null; pending: boolean; onCancel: () => void; onConfirm: () => void }) {
  const reduceMotion = useReducedMotion();
  return (
    <AnimatePresence>
      {target ? (
        <motion.div className="assistantDialogBackdrop" initial={reduceMotion ? false : { opacity: 0 }} animate={reduceMotion ? undefined : { opacity: 1 }} exit={reduceMotion ? undefined : { opacity: 0 }}>
          <motion.div
            className="assistantConfirmDialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="archive-assistant-title"
            initial={reduceMotion ? false : { opacity: 0, y: 18, scale: 0.98 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 12, scale: 0.98 }}
          >
            <div className="assistantConfirmIcon" aria-hidden="true"><Archive size={22} /></div>
            <h3 id="archive-assistant-title">Archive assistant?</h3>
            <p>{target.display_name} will be removed from active assistant management. Existing backend archive behavior is preserved.</p>
            <div className="assistantConfirmActions">
              <button type="button" className="assistantAction" onClick={onCancel} disabled={pending}>Cancel</button>
              <button type="button" className="assistantAction danger solid" onClick={onConfirm} disabled={pending}>
                {pending ? <Loader2 size={15} aria-hidden="true" className="spinIcon" /> : <Archive size={15} aria-hidden="true" />}
                {pending ? "Archiving" : "Archive"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export function AssistantEmptyState() {
  const reduceMotion = useReducedMotion();
  return (
    <section className="assistantEmpty premiumAssistantEmpty" aria-labelledby="assistant-empty-title">
      <motion.div className="assistantEmptyArt premiumAssistantEmptyArt" aria-hidden="true" initial={reduceMotion ? false : { opacity: 0, y: 18 }} animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}>
        <div className="assistantEmptyLogo">Y</div>
        <div className="assistantEmptyPanel panelOne" />
        <div className="assistantEmptyPanel panelTwo" />
      </motion.div>
      <p className="assistantEyebrow">Welcome to Conversa</p>
      <h2 id="assistant-empty-title">Create your first AI assistant</h2>
      <p>Start with a secure assistant, connect approved knowledge, test responses, then publish the widget when it is ready.</p>
      <Link className="assistantPrimaryCta large" href="/assistants/new"><Plus size={19} aria-hidden="true" />Create Assistant</Link>
    </section>
  );
}

function AssistantNoResults() {
  return (
    <div className="assistantNoResults premiumAssistantNoResults">
      <Bot size={30} aria-hidden="true" />
      <h3>No assistants match this view</h3>
      <p>Adjust search, status, or sort controls to show assistants in this workspace.</p>
    </div>
  );
}

export function AssistantDashboardSkeleton() {
  return (
    <section className="assistantPage assistantDashboardPage" aria-label="Loading My AI Assistants">
      <div className="assistantDashboardHeader assistantSkeletonBlock" />
      <div className="assistantMetrics">
        {Array.from({ length: 4 }, (_, index) => <div className="assistantMetricCard assistantSkeletonBlock" key={index} />)}
      </div>
      <div className="assistantControlSurface assistantSkeletonBlock" />
      <div className="assistantCollection assistantCollectionGrid">
        {Array.from({ length: 4 }, (_, index) => <div className="premiumAssistantCard assistantSkeletonBlock" key={index} />)}
      </div>
    </section>
  );
}

export function AssistantDashboardError({ message, retryHref = "/dashboard" }: { message: string; retryHref?: string }) {
  return (
    <section className="assistantDashboardError" role="alert" aria-labelledby="assistant-error-title">
      <XCircle size={28} aria-hidden="true" />
      <p className="assistantEyebrow">Assistant dashboard unavailable</p>
      <h2 id="assistant-error-title">We could not load your assistants.</h2>
      <p>{message}</p>
      <Link className="assistantPrimaryCta" href={retryHref}>Retry</Link>
    </section>
  );
}

export function AssistantStatusBadge({ status }: { status: AssistantStatus }) {
  const Icon = lifecycleMeta[status].icon;
  return <span className={`assistantStatus premiumAssistantStatus status${status}`} aria-label={`Status: ${status}`}><Icon size={13} aria-hidden="true" />{status}</span>;
}

export function assistantLifecycle(widget: WidgetSummary | WidgetDetail): AssistantStatus {
  if (widget.operational_status === "archived") return "Archived";
  if (widget.publication_status === "published") return "Published";
  if (widget.operational_status === "training") return "Training";
  if (widget.operational_status === "enabled" && !widget.draft_dirty) return "Ready";
  return "Draft";
}

function buildAssistantCards(assistants: WidgetDetail[], data: OverviewData): AssistantCardModel[] {
  return assistants.map((assistant) => ({
    ...assistant,
    lifecycle: assistantLifecycle(assistant),
    knowledgeCount: assistant.draft?.configuration.knowledge_scope_json.length ?? 0,
    conversationCount: countAssistantConversations(data.conversations, assistant),
    description: assistant.draft?.configuration.welcome_message || "Source-grounded assistant configured for this workspace.",
  }));
}

function buildAssistantMetrics(cards: AssistantCardModel[]) {
  const readyOrPublished = cards.filter((assistant) => assistant.lifecycle === "Ready" || assistant.lifecycle === "Published").length;
  const trainingOrDraft = cards.filter((assistant) => assistant.lifecycle === "Training" || assistant.lifecycle === "Draft").length;
  const archived = cards.filter((assistant) => assistant.lifecycle === "Archived").length;
  const knowledge = cards.reduce((total, assistant) => total + assistant.knowledgeCount, 0);
  return [
    { label: "Total assistants", value: cards.length, helper: "Loaded from workspace assistants", icon: Bot },
    { label: "Ready or published", value: readyOrPublished, helper: "Available for testing or deployment", icon: CheckCircle2 },
    { label: "Training or draft", value: trainingOrDraft, helper: "Needs review before production", icon: Clock3 },
    { label: archived > 0 ? "Archived assistants" : "Knowledge sources", value: archived > 0 ? archived : knowledge, helper: archived > 0 ? "Excluded from active assistant work" : "Assigned across loaded assistants", icon: archived > 0 ? Archive : FileText },
  ];
}

function filterAndSortAssistants(cards: AssistantCardModel[], query: string, status: StatusFilter, sort: SortOption) {
  const normalizedQuery = query.trim().toLowerCase();
  return cards
    .filter((assistant) => !normalizedQuery || `${assistant.display_name} ${assistant.description}`.toLowerCase().includes(normalizedQuery))
    .filter((assistant) => status === "all" || assistant.lifecycle === status)
    .sort((a, b) => {
      if (sort === "name-asc") return a.display_name.localeCompare(b.display_name);
      if (sort === "name-desc") return b.display_name.localeCompare(a.display_name);
      if (sort === "status-asc") return lifecycleOrder[a.lifecycle] - lifecycleOrder[b.lifecycle] || a.display_name.localeCompare(b.display_name);
      const left = new Date(a.updated_at).getTime();
      const right = new Date(b.updated_at).getTime();
      return sort === "updated-desc" ? right - left : left - right;
    });
}

function countAssistantConversations(conversations: OverviewData["conversations"], assistant: WidgetSummary) {
  return conversations.filter((conversation) => {
    const metadata = (conversation.metadata ?? {}) as Record<string, unknown>;
    return metadata.widget_id === assistant.id || metadata.assistant_id === assistant.id || metadata.public_identifier === assistant.public_identifier || conversation.assistant_id === assistant.id;
  }).length;
}

function widgetStatusLabel(assistant: WidgetSummary) {
  if (assistant.operational_status === "archived") return "Archived";
  if (assistant.publication_status === "published") return "Published";
  if (assistant.draft_dirty) return "Draft changes";
  return "Ready";
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(value));
}

function getSelectedAssistantId(workspaceId: string) {
  if (typeof window === "undefined") return null;
  const url = new URL(window.location.href);
  return url.searchParams.get("assistant") ?? window.localStorage.getItem(`yoranix:selected-assistant:${workspaceId}`);
}

function messageForAssistantError(error: unknown, fallback: string) {
  if (isDashboardApiError(error)) {
    if (error.kind === "forbidden") return "You do not have permission to manage assistants in this workspace.";
    if (error.kind === "not_found") return "This assistant is no longer available.";
    if (error.kind === "validation") return "The assistant is not in a valid state for this action.";
  }
  return fallback;
}
