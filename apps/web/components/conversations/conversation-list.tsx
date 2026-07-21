import Link from "next/link";

import type { ConversationSummary } from "../../lib/api/types";
import { ConversationStatusBadge } from "./conversation-status-badge";

type ConversationListProps = {
  conversations: ConversationSummary[];
};

export function ConversationList({ conversations }: ConversationListProps) {
  return (
    <div className="conversationList" aria-label="Conversation history results">
      {conversations.map((conversation) => (
        <article className="conversationRow" key={conversation.id}>
          <div className="conversationRowMain">
            <div className="conversationRowTitleLine">
              <h2>
                <Link href={`/conversations/${conversation.id}`}>
                  {conversation.title || `Conversation ${conversation.id.slice(0, 8)}`}
                </Link>
              </h2>
              <ConversationStatusBadge status={conversation.status} />
            </div>
            <p>{conversation.last_message_preview || "No messages have been recorded yet."}</p>
          </div>
          <dl className="conversationFacts">
            <div>
              <dt>Channel</dt>
              <dd>{formatEnum(conversation.channel)}</dd>
            </div>
            <div>
              <dt>Messages</dt>
              <dd>{conversation.message_count}</dd>
            </div>
            <div>
              <dt>Started</dt>
              <dd>{formatDate(conversation.started_at)}</dd>
            </div>
            <div>
              <dt>Last message</dt>
              <dd>{conversation.last_message_at ? formatDate(conversation.last_message_at) : "None"}</dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
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
