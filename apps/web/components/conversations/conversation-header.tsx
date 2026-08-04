import { BarChart3, Layers, MessageSquare, ShieldAlert } from "lucide-react";
import Link from "next/link";

import type { ConversationDetail } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { assistantLifecycle, AssistantStatusBadge } from "../assistants/assistant-management";
import { ConversationStatusBadge } from "./conversation-status-badge";
import { formatDate, formatEnum } from "./conversation-list";

export function ConversationsListHeader({
  assistant,
  visibleCount,
  periodLabel,
}: {
  assistant: WidgetDetail;
  visibleCount: number;
  periodLabel: string;
}) {
  const lifecycle = assistantLifecycle(assistant);
  return (
    <header className="premiumConversationsHero">
      <div className="conversationsHeroMain">
        <div>
          <p className="eyebrow">Conversation history</p>
          <h2 id="conversation-title">Conversations</h2>
          <p>Review {assistant.display_name}&rsquo;s tenant-scoped chats, fallback moments, and source-grounded answers.</p>
          <div className="conversationsHeroMeta" aria-label="Assistant state summary">
            <AssistantStatusBadge status={lifecycle} />
            <span>{visibleCount} conversation{visibleCount === 1 ? "" : "s"} on this page</span>
            <span>{periodLabel}</span>
          </div>
        </div>
      </div>
      <ConversationQuickLinks assistantId={assistant.id} />
    </header>
  );
}

export function ConversationDetailHeader({
  conversation,
  assistant,
}: {
  conversation: ConversationDetail;
  assistant: WidgetDetail;
}) {
  return (
    <header className="premiumConversationDetailHero">
      <div className="conversationsHeroMain">
        <div>
          <p className="eyebrow">Conversation detail</p>
          <h2 id="detail-title">{conversation.title || `Conversation ${conversation.id.slice(0, 8)}`}</h2>
          <p>Messages are shown in deterministic sequence with citations attached to the assistant answer that used them.</p>
          <div className="conversationsHeroMeta" aria-label="Conversation state summary">
            <ConversationStatusBadge status={conversation.status} />
            <span>Assistant {assistant.display_name}</span>
            <span>{conversation.messages.length} message{conversation.messages.length === 1 ? "" : "s"}</span>
          </div>
        </div>
      </div>

      <dl className="detailMeta premiumDetailMeta">
        <div><dt>Started</dt><dd>{formatDate(conversation.started_at)}</dd></div>
        <div><dt>Last message</dt><dd>{conversation.last_message_at ? formatDate(conversation.last_message_at) : "None"}</dd></div>
        <div><dt>Updated</dt><dd>{formatDate(conversation.updated_at)}</dd></div>
        <div><dt>Channel</dt><dd>{formatEnum(conversation.channel)}</dd></div>
      </dl>

      <ConversationQuickLinks assistantId={assistant.id} />
    </header>
  );
}

function ConversationQuickLinks({ assistantId }: { assistantId: string }) {
  return (
    <nav className="conversationQuickLinks" aria-label="Assistant quick links">
      <Link href={`/chatbot?assistant=${assistantId}`}><MessageSquare size={15} aria-hidden="true" />Playground</Link>
      <Link href={`/analytics?assistant=${assistantId}`}><BarChart3 size={15} aria-hidden="true" />Analytics</Link>
      <Link href={`/review/unanswered?assistant=${assistantId}`}><ShieldAlert size={15} aria-hidden="true" />Knowledge Gaps</Link>
      <Link href={`/dashboard`}><Layers size={15} aria-hidden="true" />Switch assistant</Link>
    </nav>
  );
}

export function ConversationArchivedNotice() {
  return (
    <p className="conversationArchivedNotice" role="status">
      <ShieldAlert size={15} aria-hidden="true" />
      This assistant is archived. Conversation history remains available for review.
    </p>
  );
}
