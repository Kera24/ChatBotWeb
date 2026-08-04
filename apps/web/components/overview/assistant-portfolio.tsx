import { ArrowRight, Plus, Rocket } from "lucide-react";
import Link from "next/link";

import type { ConversationSummary } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { assistantLifecycle, AssistantStatusBadge } from "../assistants/assistant-management";

export type AssistantPortfolioCard = {
  id: string;
  name: string;
  lifecycle: ReturnType<typeof assistantLifecycle>;
  knowledgeCount: number;
  published: boolean;
  updatedAt: string;
  conversationCount: number;
  actionRequired: string | null;
  primaryAction: { label: string; href: string };
};

export function buildAssistantPortfolio(assistants: WidgetDetail[], conversations: ConversationSummary[]): AssistantPortfolioCard[] {
  return assistants
    .map((assistant) => {
      const lifecycle = assistantLifecycle(assistant);
      const knowledgeCount = assistant.draft?.configuration.knowledge_scope_json.length ?? 0;
      const conversationCount = countAssistantConversations(conversations, assistant);
      const actionRequired = deriveActionRequired(assistant, lifecycle, knowledgeCount);
      const primaryAction = derivePrimaryAction(assistant, lifecycle, knowledgeCount);
      return {
        id: assistant.id,
        name: assistant.display_name,
        lifecycle,
        knowledgeCount,
        published: assistant.publication_status === "published",
        updatedAt: assistant.updated_at,
        conversationCount,
        actionRequired,
        primaryAction,
      };
    })
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
}

function countAssistantConversations(conversations: ConversationSummary[], assistant: WidgetDetail) {
  return conversations.filter((conversation) => {
    const metadata = (conversation.metadata ?? {}) as Record<string, unknown>;
    return conversation.assistant_id === assistant.id || metadata.widget_id === assistant.id || metadata.assistant_id === assistant.id || metadata.public_identifier === assistant.public_identifier;
  }).length;
}

function deriveActionRequired(assistant: WidgetDetail, lifecycle: ReturnType<typeof assistantLifecycle>, knowledgeCount: number) {
  if (knowledgeCount === 0) return "Add knowledge before publishing.";
  if (lifecycle === "Draft" && assistant.draft_dirty) return "Unpublished draft changes.";
  if (lifecycle !== "Published") return "Not yet published.";
  return null;
}

function derivePrimaryAction(assistant: WidgetDetail, lifecycle: ReturnType<typeof assistantLifecycle>, knowledgeCount: number) {
  if (knowledgeCount === 0) return { label: "Add knowledge", href: `/knowledge?assistant=${assistant.id}` };
  if (lifecycle !== "Published") return { label: "Review and publish", href: `/assistants/${assistant.id}?tab=widget&assistant=${assistant.id}` };
  return { label: "Open assistant", href: `/assistants/${assistant.id}?assistant=${assistant.id}` };
}

export function AssistantPortfolio({ cards, totalAssistants }: { cards: AssistantPortfolioCard[]; totalAssistants: number }) {
  const visible = cards.slice(0, 6);

  return (
    <section className="overviewPanel assistantPortfolioPanel" aria-labelledby="portfolio-title">
      <div className="overviewPanelHeader">
        <div>
          <p className="sectionKicker">Assistant portfolio</p>
          <h3 id="portfolio-title">Most recently active assistants</h3>
        </div>
        <Link className="smallButton" href="/dashboard">View all assistants<ArrowRight size={13} aria-hidden="true" /></Link>
      </div>
      <div className="assistantPortfolioGrid" role="list" aria-label="Assistant portfolio">
        {visible.map((card) => (
          <article className="assistantPortfolioCard" role="listitem" key={card.id}>
            <div className="assistantPortfolioTop">
              <h4>{card.name}</h4>
              <AssistantStatusBadge status={card.lifecycle} />
            </div>
            <dl className="assistantPortfolioFacts">
              <div><dt>Knowledge</dt><dd>{card.knowledgeCount} source{card.knowledgeCount === 1 ? "" : "s"}</dd></div>
              <div><dt>Conversations</dt><dd>{card.conversationCount}</dd></div>
              <div><dt>Updated</dt><dd>{formatDate(card.updatedAt)}</dd></div>
            </dl>
            {card.actionRequired ? <p className="assistantPortfolioAction"><Rocket size={13} aria-hidden="true" />{card.actionRequired}</p> : null}
            <Link className="smallButton assistantPortfolioLink" href={card.primaryAction.href}>{card.primaryAction.label}<ArrowRight size={13} aria-hidden="true" /></Link>
          </article>
        ))}
      </div>
      {totalAssistants > visible.length ? <p className="reviewFilterNote">Showing {visible.length} of {totalAssistants} assistants. <Link href="/dashboard">View the complete directory</Link>.</p> : null}
    </section>
  );
}

export function NoAssistantsPortfolioState() {
  return (
    <section className="overviewPanel assistantPortfolioPanel" aria-labelledby="portfolio-title">
      <div className="overviewPanelHeader">
        <div>
          <p className="sectionKicker">Assistant portfolio</p>
          <h3 id="portfolio-title">Most recently active assistants</h3>
        </div>
      </div>
      <div className="overviewEmptyState">
        <Plus size={20} aria-hidden="true" />
        <h4>No assistants yet</h4>
        <p>Create your first assistant to start building knowledge and testing conversations.</p>
        <Link className="assistantAction primary" href="/assistants/new"><Plus size={15} aria-hidden="true" />Create assistant</Link>
      </div>
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}
