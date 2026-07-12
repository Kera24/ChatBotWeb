import type { ConversationMessage } from "../../lib/api/types";
import { CitationList } from "./citation-list";
import { ConversationStatusBadge } from "./conversation-status-badge";
import { TechnicalDetails } from "./technical-details";

type MessageThreadProps = {
  messages: ConversationMessage[];
};

export function MessageThread({ messages }: MessageThreadProps) {
  return (
    <section className="messageThread" aria-label="Conversation messages">
      {messages.map((message) => (
        <article className={`messageBubble message-${message.role}`} key={message.id}>
          <div className="messageHeader">
            <span>{message.role === "assistant" ? "Assistant" : message.role === "user" ? "User" : message.role}</span>
            {message.answer_state ? <ConversationStatusBadge status={message.answer_state} answerState /> : null}
          </div>
          <p>{message.content}</p>
          <CitationList citations={message.citations} />
          {message.role === "assistant" ? <TechnicalDetails message={message} /> : null}
        </article>
      ))}
    </section>
  );
}
