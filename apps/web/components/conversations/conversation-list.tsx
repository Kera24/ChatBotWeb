import { Layers, MessagesSquare, Clock3 } from "lucide-react";
import Link from "next/link";

import type { ConversationSummary } from "../../lib/api/types";
import { ConversationStatusBadge } from "./conversation-status-badge";

type ConversationInboxProps = {
  conversations: ConversationSummary[];
  assistantId: string;
  assistantLabel?: string;
};

export function ConversationInbox({ conversations, assistantId, assistantLabel }: ConversationInboxProps) {
  return (
    <div className="conversationInbox" role="list" aria-label="Conversation history results">
      {conversations.map((conversation) => (
        <ConversationListItem key={conversation.id} conversation={conversation} assistantId={assistantId} assistantLabel={assistantLabel} />
      ))}
    </div>
  );
}

export function ConversationListItem({ conversation, assistantId, assistantLabel }: { conversation: ConversationSummary; assistantId: string; assistantLabel?: string }) {
  const linkAssistantId = conversation.assistant_id || assistantId;
  const href = linkAssistantId ? `/conversations/${conversation.id}?assistant=${linkAssistantId}` : `/conversations/${conversation.id}`;
  const title = conversation.title || `Conversation ${conversation.id.slice(0, 8)}`;
  const preview = conversation.last_message_preview || "No messages have been recorded yet.";

  return (
    <article className="conversationCard" role="listitem">
      <Link
        className="conversationCardLink"
        href={href}
        aria-label={`${title}. ${formatEnum(conversation.status)} conversation on ${formatEnum(conversation.channel)}. ${conversation.message_count} message${conversation.message_count === 1 ? "" : "s"}. Started ${formatDate(conversation.started_at)}.`}
      >
        <div className="conversationCardTop">
          <h3>{title}</h3>
          <ConversationStatusBadge status={conversation.status} />
        </div>
        <p className="conversationCardPreview">{preview}</p>
        <div className="conversationCardMeta" aria-hidden="true">
          {assistantLabel ? <span className="conversationCardAssistant"><Layers size={13} />{assistantLabel}</span> : null}
          <span>{formatEnum(conversation.channel)}</span>
          <span><MessagesSquare size={13} />{conversation.message_count} message{conversation.message_count === 1 ? "" : "s"}</span>
          <span><Clock3 size={13} />Started {formatDate(conversation.started_at)}</span>
          <span>Last activity {conversation.last_message_at ? formatDate(conversation.last_message_at) : "None"}</span>
        </div>
      </Link>
    </article>
  );
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatEnum(value: string | null | undefined) {
  return (value ?? "unknown").replace(/_/g, " ");
}
