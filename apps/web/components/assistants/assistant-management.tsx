"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Archive, BarChart3, Bot, Copy, ExternalLink, FileText, Pencil, Plus, Rocket, Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { archiveWidget, duplicateWidget, type WidgetDetail, type WidgetSummary } from "../../lib/api/widgets";
import { isDashboardApiError } from "../../lib/api/errors";
import type { OverviewData } from "../../lib/api/overview";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type AssistantManagementProps = {
  session: DevelopmentDashboardSession;
  assistants: WidgetDetail[];
  data: OverviewData;
};

type AssistantStatus = "Draft" | "Training" | "Ready" | "Published" | "Archived";
type StatusFilter = "all" | AssistantStatus;

type AssistantCardModel = WidgetDetail & {
  lifecycle: AssistantStatus;
  knowledgeCount: number;
  conversationCount: number;
};

const statusFilters: StatusFilter[] = ["all", "Draft", "Training", "Ready", "Published", "Archived"];

export function AssistantManagement({ session, assistants, data }: AssistantManagementProps) {
  const reduceMotion = useReducedMotion();
  const [items, setItems] = useState<WidgetDetail[]>(assistants);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [sort, setSort] = useState<"updated-desc" | "updated-asc">("updated-desc");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cards = useMemo(() => buildAssistantCards(items, data), [items, data]);
  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return cards
      .filter((assistant) => !normalizedQuery || assistant.display_name.toLowerCase().includes(normalizedQuery))
      .filter((assistant) => status === "all" || assistant.lifecycle === status)
      .sort((a, b) => {
        const left = new Date(a.updated_at).getTime();
        const right = new Date(b.updated_at).getTime();
        return sort === "updated-desc" ? right - left : left - right;
      });
  }, [cards, query, sort, status]);

  async function onDuplicate(assistant: WidgetDetail) {
    setBusyId(assistant.id);
    setError(null);
    try {
      const response = await duplicateWidget(session, assistant.id);
      setItems((current) => [response.data, ...current]);
    } catch (caught) {
      setError(messageForAssistantError(caught, "Assistant could not be duplicated."));
    } finally {
      setBusyId(null);
    }
  }

  async function onArchive(assistant: WidgetDetail) {
    setBusyId(assistant.id);
    setError(null);
    try {
      await archiveWidget(session, assistant.id);
      setItems((current) => current.filter((item) => item.id !== assistant.id));
    } catch (caught) {
      setError(messageForAssistantError(caught, "Assistant could not be archived."));
    } finally {
      setBusyId(null);
    }
  }

  if (items.length === 0) {
    return <AssistantEmptyState />;
  }

  return (
    <section className="assistantPage" aria-labelledby="assistants-title">
      <motion.div
        className="assistantHero"
        initial={reduceMotion ? false : { opacity: 0, y: 18 }}
        animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
      >
        <div>
          <p className="eyebrow">Workspace assistants</p>
          <h2 id="assistants-title">My AI Assistants</h2>
          <p>Create, publish, monitor, and refine every AI assistant in {session.workspaceName} from one secure workspace.</p>
        </div>
        <Link className="assistantPrimaryCta" href="/assistants/new">
          <Plus size={18} aria-hidden="true" />
          Create Assistant
        </Link>
      </motion.div>

      <section className="assistantControlBar" aria-label="Assistant search and filters">
        <label className="assistantSearch">
          <Search size={17} aria-hidden="true" />
          <span className="srOnly">Search assistants by name</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search assistants" />
        </label>
        <label className="assistantSelect">
          <SlidersHorizontal size={17} aria-hidden="true" />
          <span className="srOnly">Filter assistants by status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)}>
            {statusFilters.map((option) => <option key={option} value={option}>{option === "all" ? "All statuses" : option}</option>)}
          </select>
        </label>
        <label className="assistantSelect">
          <span className="srOnly">Sort assistants by last updated</span>
          <select value={sort} onChange={(event) => setSort(event.target.value as "updated-desc" | "updated-asc")}>
            <option value="updated-desc">Newest updated</option>
            <option value="updated-asc">Oldest updated</option>
          </select>
        </label>
      </section>

      {error ? <div className="assistantError" role="alert">{error}</div> : null}

      {filtered.length === 0 ? (
        <div className="assistantNoResults">
          <Bot size={26} aria-hidden="true" />
          <h3>No assistants match this view</h3>
          <p>Adjust the search or status filter to show assistants in this workspace.</p>
        </div>
      ) : (
        <motion.div className="assistantGrid" initial={false} animate={{ opacity: 1 }}>
          {filtered.map((assistant, index) => (
            <motion.article
              className="assistantCard"
              key={assistant.id}
              initial={reduceMotion ? false : { opacity: 0, y: 16 }}
              animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
              transition={{ duration: 0.28, delay: Math.min(index * 0.04, 0.18) }}
            >
              <div className="assistantCardHeader">
                <div className="assistantIcon" aria-hidden="true"><Bot size={21} /></div>
                <div>
                  <h3>{assistant.display_name}</h3>
                  <p>Updated {formatDate(assistant.updated_at)}</p>
                </div>
                <AssistantStatusBadge status={assistant.lifecycle} />
              </div>

              <dl className="assistantStats">
                <div><dt>Knowledge Documents</dt><dd><FileText size={16} aria-hidden="true" />{assistant.knowledgeCount}</dd></div>
                <div><dt>Widget Status</dt><dd>{widgetStatusLabel(assistant)}</dd></div>
                <div><dt>Conversations</dt><dd>{assistant.conversationCount}</dd></div>
                <div><dt>Last Updated</dt><dd>{formatShortDate(assistant.updated_at)}</dd></div>
              </dl>

              <div className="assistantActions" aria-label={`Actions for ${assistant.display_name}`}>
                <Link className="assistantAction primary" href={`/assistants/${assistant.id}`}><ExternalLink size={15} aria-hidden="true" />Open</Link>
                <Link className="assistantAction" href={`/assistants/${assistant.id}?tab=settings`}><Pencil size={15} aria-hidden="true" />Edit</Link>
                <Link className="assistantAction" href={`/assistants/${assistant.id}?tab=analytics`}><BarChart3 size={15} aria-hidden="true" />Analytics</Link>
                <Link className="assistantAction" href={`/assistants/${assistant.id}?tab=widget`}><Rocket size={15} aria-hidden="true" />Publish</Link>
                <button className="assistantAction" type="button" onClick={() => onDuplicate(assistant)} disabled={busyId === assistant.id}><Copy size={15} aria-hidden="true" />Duplicate</button>
                <button className="assistantAction danger" type="button" onClick={() => onArchive(assistant)} disabled={busyId === assistant.id}><Archive size={15} aria-hidden="true" />Archive</button>
              </div>
            </motion.article>
          ))}
        </motion.div>
      )}
    </section>
  );
}

export function AssistantEmptyState() {
  return (
    <section className="assistantEmpty" aria-labelledby="assistant-empty-title">
      <div className="assistantEmptyArt" aria-hidden="true">
        <div className="assistantEmptyLogo">Y</div>
        <div className="assistantEmptyPanel panelOne" />
        <div className="assistantEmptyPanel panelTwo" />
      </div>
      <p className="eyebrow">Welcome to Yoranix</p>
      <h2 id="assistant-empty-title">Let&apos;s build your first AI Assistant.</h2>
      <p>Start with a secure assistant, connect approved knowledge, test responses, then publish the widget when it is ready.</p>
      <Link className="assistantPrimaryCta large" href="/assistants/new"><Plus size={19} aria-hidden="true" />Create Assistant</Link>
    </section>
  );
}

export function AssistantStatusBadge({ status }: { status: AssistantStatus }) {
  return <span className={`assistantStatus status${status}`}>{status}</span>;
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
  }));
}

function countAssistantConversations(conversations: OverviewData["conversations"], assistant: WidgetSummary) {
  return conversations.filter((conversation) => {
    const metadata = (conversation.metadata ?? {}) as Record<string, unknown>;
    return metadata.widget_id === assistant.id || metadata.assistant_id === assistant.id || metadata.public_identifier === assistant.public_identifier;
  }).length;
}

function widgetStatusLabel(assistant: WidgetSummary) {
  if (assistant.operational_status === "archived") return "Archived";
  if (assistant.publication_status === "published") return "Published";
  if (assistant.draft_dirty) return "Draft changes";
  return "Ready";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function formatShortDate(value: string) {
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(new Date(value));
}

function messageForAssistantError(error: unknown, fallback: string) {
  if (isDashboardApiError(error)) {
    if (error.kind === "forbidden") return "You do not have permission to manage assistants in this workspace.";
    if (error.kind === "not_found") return "This assistant is no longer available.";
    if (error.kind === "validation") return "The assistant is not in a valid state for this action.";
  }
  return fallback;
}
