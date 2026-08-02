"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Archive, BarChart3, Bot, FileText, MessageSquare, Rocket, Settings, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type ComponentType } from "react";

import { archiveWidget, duplicateWidget, type WidgetDetail, type WidgetEmbedMetadata, type WidgetInstallationStatus, type WidgetKnowledgeOption, type WidgetOrigin, type WidgetRevisionDetail, type WidgetSupportedSdkVersionsResponse } from "../../lib/api/widgets";
import type { OverviewData } from "../../lib/api/overview";
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

const tabs: Array<{ id: AssistantTab; label: string; icon: ComponentType<{ size?: number }> }> = [
  { id: "overview", label: "Overview", icon: Bot },
  { id: "knowledge", label: "Knowledge", icon: FileText },
  { id: "playground", label: "Playground", icon: MessageSquare },
  { id: "widget", label: "Widget", icon: Rocket },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
  { id: "settings", label: "Settings", icon: Settings },
];

export function AssistantDetailClient(props: AssistantDetailClientProps) {
  const searchParams = useSearchParams();
  const reduceMotion = useReducedMotion();
  const selected = coerceTab(searchParams.get("tab"));
  const widget = props.initialWidget;

  return (
    <section className="assistantDetailPage" aria-labelledby="assistant-detail-title">
      <motion.header
        className="assistantDetailHero"
        initial={reduceMotion ? false : { opacity: 0, y: 16 }}
        animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      >
        <div>
          <p className="eyebrow">Assistant Overview</p>
          <h2 id="assistant-detail-title">{widget.display_name}</h2>
          <p>Manage this assistant&apos;s knowledge, playground testing, website widget, analytics, and lifecycle settings.</p>
        </div>
        <AssistantStatusBadge status={assistantLifecycle(widget)} />
      </motion.header>

      <nav className="assistantTabs" aria-label="Assistant sections">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = selected === tab.id;
          return <Link key={tab.id} className={`assistantTab${active ? " active" : ""}`} href={`/assistants/${widget.id}?tab=${tab.id}`} aria-current={active ? "page" : undefined}><Icon size={16} aria-hidden="true" />{tab.label}</Link>;
        })}
      </nav>

      {selected === "overview" ? <OverviewTab widget={widget} draft={props.initialDraft} embed={props.initialEmbed} overviewData={props.overviewData} /> : null}
      {selected === "knowledge" ? <KnowledgeTab widget={widget} draft={props.initialDraft} knowledgeOptions={props.initialKnowledgeOptions} /> : null}
      {selected === "playground" ? <PlaygroundTab session={props.session} /> : null}
      {selected === "widget" ? <WidgetDetailClient session={props.session} initialWidget={props.initialWidget} initialDraft={props.initialDraft} initialOrigins={props.initialOrigins} initialEmbed={props.initialEmbed} sdkVersions={props.initialSdkVersions} knowledgeOptions={props.initialKnowledgeOptions} initialRevisions={props.initialRevisions} initialInstallationStatus={props.initialInstallationStatus} /> : null}
      {selected === "analytics" ? <AnalyticsTab widget={widget} overviewData={props.overviewData} /> : null}
      {selected === "settings" ? <SettingsTab session={props.session} widget={widget} /> : null}
    </section>
  );
}

function OverviewTab({ widget, draft, embed, overviewData }: { widget: WidgetDetail; draft: WidgetRevisionDetail; embed: WidgetEmbedMetadata; overviewData: OverviewData }) {
  const knowledgeCount = draft.configuration.knowledge_scope_json.length;
  const conversationCount = countAssistantConversations(overviewData, widget);
  return (
    <div className="assistantDetailGrid">
      <article className="assistantDetailPanel wide">
        <h3>Operating Summary</h3>
        <p>{draft.configuration.welcome_message}</p>
        <dl className="assistantStats compact">
          <div><dt>Status</dt><dd>{assistantLifecycle(widget)}</dd></div>
          <div><dt>Knowledge Documents</dt><dd>{knowledgeCount}</dd></div>
          <div><dt>Widget</dt><dd>{embed.published ? "Published" : "Draft"}</dd></div>
          <div><dt>Conversations</dt><dd>{conversationCount}</dd></div>
        </dl>
      </article>
      <article className="assistantDetailPanel">
        <h3>Guardrails</h3>
        <ul className="assistantCheckList">
          <li><ShieldCheck size={16} aria-hidden="true" />Citations {draft.configuration.show_citations ? "enabled" : "disabled"}</li>
          <li><ShieldCheck size={16} aria-hidden="true" />Conversation history {draft.configuration.allow_conversation_history ? "enabled" : "disabled"}</li>
          <li><ShieldCheck size={16} aria-hidden="true" />Theme follows Yoranix brand defaults</li>
        </ul>
      </article>
      <article className="assistantDetailPanel">
        <h3>Next Action</h3>
        <p>{embed.active ? "Your assistant widget is active. Review analytics and continue improving knowledge coverage." : "Finish widget readiness checks, then publish when the assistant is ready for customers."}</p>
        <Link className="assistantAction primary" href={`/assistants/${widget.id}?tab=widget`}>Open Widget</Link>
      </article>
    </div>
  );
}

function KnowledgeTab({ widget, draft, knowledgeOptions }: { widget: WidgetDetail; draft: WidgetRevisionDetail; knowledgeOptions: WidgetKnowledgeOption[] }) {
  const selected = new Set(draft.configuration.knowledge_scope_json);
  const chosen = knowledgeOptions.filter((option) => selected.has(option.id));
  return (
    <section className="assistantDetailPanel wide">
      <div className="assistantPanelHeader">
        <div>
          <h3>Knowledge</h3>
          <p>{chosen.length} approved documents are scoped to this assistant.</p>
        </div>
        <Link className="assistantAction primary" href={`/assistants/${widget.id}?tab=widget`}>Manage Sources</Link>
      </div>
      {chosen.length === 0 ? <p className="assistantMuted">No documents are scoped yet. Add sources from the Widget tab or Knowledge Base.</p> : (
        <div className="assistantKnowledgeList">
          {chosen.map((item) => <article key={item.id}><strong>{item.title}</strong><span>{item.type} - {item.readiness}</span></article>)}
        </div>
      )}
    </section>
  );
}

function PlaygroundTab({ session }: { session: DevelopmentDashboardSession }) {
  return (
    <div className="assistantPlaygroundShell">
      <ChatbotClient session={session} />
    </div>
  );
}

function AnalyticsTab({ widget, overviewData }: { widget: WidgetDetail; overviewData: OverviewData }) {
  const assistantConversations = countAssistantConversations(overviewData, widget);
  return (
    <div className="assistantDetailGrid">
      <article className="assistantDetailPanel">
        <h3>Assistant Conversations</h3>
        <strong className="assistantMetricValue">{assistantConversations}</strong>
        <p>Counted from conversation metadata when a widget or assistant identifier is present.</p>
      </article>
      <article className="assistantDetailPanel">
        <h3>Workspace Conversations</h3>
        <strong className="assistantMetricValue">{overviewData.conversations.length}</strong>
        <p>Total visible conversations in this workspace.</p>
      </article>
      <article className="assistantDetailPanel">
        <h3>Knowledge Gaps</h3>
        <strong className="assistantMetricValue">{overviewData.reviewTotal}</strong>
        <p>Unanswered review items that can guide assistant improvement.</p>
      </article>
    </div>
  );
}

function SettingsTab({ session, widget }: { session: DevelopmentDashboardSession; widget: WidgetDetail }) {
  const router = useRouter();
  const [busy, setBusy] = useState<"duplicate" | "archive" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function duplicate() {
    setBusy("duplicate");
    setError(null);
    try {
      const response = await duplicateWidget(session, widget.id);
      router.push(`/assistants/${response.data.id}`);
      router.refresh();
    } catch {
      setError("Assistant could not be duplicated.");
      setBusy(null);
    }
  }

  async function archive() {
    setBusy("archive");
    setError(null);
    try {
      await archiveWidget(session, widget.id);
      router.push("/dashboard");
      router.refresh();
    } catch {
      setError("Assistant could not be archived.");
      setBusy(null);
    }
  }

  return (
    <section className="assistantDetailPanel wide">
      <h3>Lifecycle Settings</h3>
      <p>Duplicate this assistant to create a new draft from the current configuration, or archive it when it should no longer appear in active workspace views.</p>
      {error ? <p className="errorText" role="alert">{error}</p> : null}
      <div className="assistantSettingsActions">
        <button className="assistantAction" type="button" onClick={duplicate} disabled={busy !== null}>Duplicate Assistant</button>
        <button className="assistantAction danger" type="button" onClick={archive} disabled={busy !== null}><Archive size={15} aria-hidden="true" />Archive Assistant</button>
      </div>
    </section>
  );
}

function coerceTab(value: string | null): AssistantTab {
  return tabs.some((tab) => tab.id === value) ? value as AssistantTab : "overview";
}

function countAssistantConversations(data: OverviewData, assistant: WidgetDetail) {
  return data.conversations.filter((conversation) => {
    const metadata = conversation.metadata ?? {};
    return metadata.widget_id === assistant.id || metadata.assistant_id === assistant.id || metadata.public_identifier === assistant.public_identifier;
  }).length;
}
