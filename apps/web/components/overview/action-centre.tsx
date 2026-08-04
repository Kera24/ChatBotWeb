import { AlertTriangle, ArrowRight, CheckCircle2, Info, ShieldAlert, type LucideIcon } from "lucide-react";
import Link from "next/link";

import type { OverviewData } from "../../lib/api/overview";
import type { ConversationSummary } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { assistantLifecycle } from "../assistants/assistant-management";

export type ActionTone = "danger" | "warning" | "info";

export type ActionItem = {
  id: string;
  tone: ActionTone;
  title: string;
  detail: string;
  href: string;
};

const TONE_ICON: Record<ActionTone, LucideIcon> = { danger: ShieldAlert, warning: AlertTriangle, info: Info };

export function buildActionItems(data: OverviewData, assistants: WidgetDetail[], session: DevelopmentDashboardSession): ActionItem[] {
  const items: ActionItem[] = [];

  if (session.onboardingComplete === false) {
    items.push({ id: "onboarding-incomplete", tone: "warning", title: "Onboarding incomplete", detail: "Finish workspace onboarding to unlock the full platform.", href: "/onboarding" });
  }

  const failedDocuments = data.documents.filter((document) => document.status === "failed").length;
  if (failedDocuments > 0) {
    items.push({ id: "failed-documents", tone: "danger", title: "Document processing failures", detail: `${failedDocuments} document${failedDocuments === 1 ? "" : "s"} failed processing and need${failedDocuments === 1 ? "s" : ""} investigation.`, href: "/knowledge" });
  }

  const assistantsWithoutKnowledge = assistants.filter((assistant) => (assistant.draft?.configuration.knowledge_scope_json.length ?? 0) === 0);
  if (assistantsWithoutKnowledge.length > 0) {
    items.push({
      id: "assistants-without-knowledge",
      tone: "warning",
      title: "Assistants with no knowledge",
      detail: `${assistantsWithoutKnowledge.length} assistant${assistantsWithoutKnowledge.length === 1 ? " has" : "s have"} no knowledge assigned: ${assistantsWithoutKnowledge.slice(0, 3).map((assistant) => assistant.display_name).join(", ")}${assistantsWithoutKnowledge.length > 3 ? "…" : ""}.`,
      href: `/knowledge?assistant=${assistantsWithoutKnowledge[0].id}`,
    });
  }

  const unpublishedAssistants = assistants.filter((assistant) => assistantLifecycle(assistant) !== "Published" && assistantLifecycle(assistant) !== "Archived");
  if (unpublishedAssistants.length > 0) {
    items.push({
      id: "unpublished-assistants",
      tone: "warning",
      title: "Unpublished assistants",
      detail: `${unpublishedAssistants.length} assistant${unpublishedAssistants.length === 1 ? " is" : "s are"} not yet published: ${unpublishedAssistants.slice(0, 3).map((assistant) => assistant.display_name).join(", ")}${unpublishedAssistants.length > 3 ? "…" : ""}.`,
      href: `/assistants/${unpublishedAssistants[0].id}?tab=widget&assistant=${unpublishedAssistants[0].id}`,
    });
  }

  const draftDirtyAssistants = assistants.filter((assistant) => assistant.draft_dirty && assistant.publication_status === "published");
  if (draftDirtyAssistants.length > 0) {
    items.push({
      id: "unpublished-draft-changes",
      tone: "info",
      title: "Unpublished draft changes",
      detail: `${draftDirtyAssistants.length} published assistant${draftDirtyAssistants.length === 1 ? " has" : "s have"} draft changes waiting to be published: ${draftDirtyAssistants.slice(0, 3).map((assistant) => assistant.display_name).join(", ")}${draftDirtyAssistants.length > 3 ? "…" : ""}.`,
      href: `/assistants/${draftDirtyAssistants[0].id}?tab=widget&assistant=${draftDirtyAssistants[0].id}`,
    });
  }

  if (data.reviewTotal > 0) {
    items.push({ id: "review-backlog", tone: "warning", title: "Unresolved knowledge gaps", detail: `${data.reviewTotal} unanswered item${data.reviewTotal === 1 ? " is" : "s are"} open for review.`, href: "/review/unanswered" });
  }

  const fallbackCount = data.reviewItems.filter((item) => item.answer_state === "fallback").length;
  if (data.reviewItems.length > 0 && fallbackCount / data.reviewItems.length >= 0.5) {
    items.push({ id: "high-fallback-volume", tone: "warning", title: "High fallback volume", detail: `${fallbackCount} of ${data.reviewItems.length} sampled open review items are fallback answers.`, href: "/review/unanswered" });
  }

  const inactiveAssistants = assistants.filter((assistant) => countAssistantConversations(data.conversations, assistant) === 0);
  if (inactiveAssistants.length > 0 && assistants.length > 0) {
    items.push({
      id: "inactive-assistants",
      tone: "info",
      title: "Inactive assistants",
      detail: `${inactiveAssistants.length} assistant${inactiveAssistants.length === 1 ? " has" : "s have"} no conversations in the recent window: ${inactiveAssistants.slice(0, 3).map((assistant) => assistant.display_name).join(", ")}${inactiveAssistants.length > 3 ? "…" : ""}.`,
      href: `/assistants/${inactiveAssistants[0].id}?tab=playground&assistant=${inactiveAssistants[0].id}`,
    });
  }

  return items;
}

function countAssistantConversations(conversations: ConversationSummary[], assistant: WidgetDetail) {
  return conversations.filter((conversation) => {
    const metadata = (conversation.metadata ?? {}) as Record<string, unknown>;
    return conversation.assistant_id === assistant.id || metadata.widget_id === assistant.id || metadata.assistant_id === assistant.id || metadata.public_identifier === assistant.public_identifier;
  }).length;
}

export function ActionCentre({ items }: { items: ActionItem[] }) {
  return (
    <section className="overviewPanel actionCentrePanel" aria-labelledby="action-centre-title">
      <div className="overviewPanelHeader">
        <div>
          <p className="sectionKicker">Needs attention</p>
          <h3 id="action-centre-title">Action centre</h3>
        </div>
      </div>
      <p className="reviewFilterNote">These are deterministic operational rules applied to existing platform data, not AI-generated recommendations.</p>
      {items.length === 0 ? (
        <div className="overviewEmptyState">
          <CheckCircle2 size={20} aria-hidden="true" />
          <h4>Nothing needs attention</h4>
          <p>No failed documents, unpublished assistants, open knowledge gaps, or inactive assistants were found.</p>
        </div>
      ) : (
        <div className="actionCentreList" role="list">
          {items.map((item) => {
            const Icon = TONE_ICON[item.tone];
            return (
              <article className={`actionCentreItem tone-${item.tone}`} role="listitem" key={item.id}>
                <span className="actionCentreIcon" aria-hidden="true"><Icon size={16} /></span>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </div>
                <Link className="smallButton" href={item.href}>Open<ArrowRight size={13} aria-hidden="true" /></Link>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
