"use client";

import Link from "next/link";
import { useMemo, useRef, useState, type FormEvent } from "react";

import { ConversationStatusBadge } from "../conversations/conversation-status-badge";
import { isDashboardApiError } from "../../lib/api/errors";
import { answerChatbotQuestion } from "../../lib/api/chatbot";
import type { RAGAnswerResponse, RAGCitation } from "../../lib/api/types";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type ChatMessage =
  | { id: string; role: "user"; content: string }
  | {
      id: string;
      role: "assistant";
      content: string;
      answerState: string;
      fallbackUsed: boolean;
      citations: RAGCitation[];
      retrievedChunkCount: number;
      latencyMs: number;
      providerKey: string;
      modelKey: string;
    };

type ChatbotClientProps = {
  session: DevelopmentDashboardSession;
};

export function ChatbotClient({ session }: ChatbotClientProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [composer, setComposer] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sequence = useRef(0);

  const canSend = composer.trim().length > 0 && !pending;
  const conversationLabel = useMemo(() => conversationId ? `Conversation ${conversationId.slice(0, 8)}` : "New dashboard test", [conversationId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = composer.trim();
    if (!query || pending) return;

    const userMessage: ChatMessage = {
      id: `local-user-${++sequence.current}`,
      role: "user",
      content: query,
    };
    setMessages((current) => [...current, userMessage]);
    setComposer("");
    setPending(true);
    setError(null);

    try {
      const response = await answerChatbotQuestion(session, { query, conversationId });
      setConversationId(response.data.conversation_id);
      setMessages((current) => [...current, assistantMessageFromResponse(response.data)]);
    } catch (caught) {
      setError(messageForChatbotError(caught));
    } finally {
      setPending(false);
    }
  }

  function startNewConversation() {
    if (pending) return;
    setMessages([]);
    setConversationId(null);
    setError(null);
    setComposer("");
  }

  return (
    <section className="chatbotPage" aria-labelledby="chatbot-title">
      <div className="chatbotHero">
        <div>
          <p className="eyebrow">Chatbot</p>
          <h2 id="chatbot-title">Test workspace answers</h2>
          <p>Ask the authenticated workspace RAG endpoint a question and review the persisted dashboard-test answer, citations, fallback state, and operational metadata.</p>
        </div>
        <div className="chatbotHeroAside">
          <strong>{messages.filter((message) => message.role === "assistant").length}</strong>
          <span>answers in this test</span>
        </div>
      </div>

      <div className="chatbotLayout">
        <section className="chatbotPanel" aria-label="Chat test">
          <div className="chatbotToolbar">
            <div>
              <span className="sectionKicker">Current thread</span>
              <strong>{conversationLabel}</strong>
            </div>
            <button type="button" className="smallButton" onClick={startNewConversation} disabled={pending || messages.length === 0}>
              New test
            </button>
          </div>

          <div className="chatbotTranscript" aria-live="polite">
            {messages.length === 0 ? (
              <div className="chatbotWelcome">
                <h3>Ask against indexed workspace knowledge</h3>
                <p>Answers are stored as the dashboard_test channel and appear in Conversation history for review.</p>
              </div>
            ) : null}
            {messages.map((message) => (
              <ChatbotMessage key={message.id} message={message} />
            ))}
            {pending ? (
              <article className="messageBubble message-assistant chatbotPending">
                <div className="messageHeader">
                  <span>Assistant</span>
                  <ConversationStatusBadge status="pending" answerState />
                </div>
                <p>Generating an answer from workspace knowledge...</p>
              </article>
            ) : null}
          </div>

          {error ? <p className="errorText" role="alert">{error}</p> : null}

          <form className="chatbotComposer" onSubmit={submit}>
            <label htmlFor="chatbot-message">Message</label>
            <textarea
              id="chatbot-message"
              value={composer}
              maxLength={4000}
              rows={3}
              placeholder="Ask a question about the indexed knowledge base"
              onChange={(event) => setComposer(event.target.value)}
            />
            <div className="chatbotComposerActions">
              <span>{composer.length}/4000</span>
              <button className="actionButton" type="submit" disabled={!canSend}>
                {pending ? "Sending" : "Send"}
              </button>
            </div>
          </form>
        </section>

        <aside className="chatbotSidePanel" aria-label="Chatbot configuration links">
          <h2>Configuration lives in Widgets</h2>
          <p>Public bot identity, welcome copy, suggested questions, allowed domains, embed settings, and public preview are managed through widget administration.</p>
          <div className="chatbotLinkList">
            <Link className="actionButton" href="/widgets">Open widget settings</Link>
            <Link className="actionButton" href="/conversations?channel=dashboard_test">Review dashboard tests</Link>
            <Link className="actionButton" href="/knowledge">Manage knowledge</Link>
          </div>
          <dl className="widgetFacts compactFacts">
            <div><dt>Mode</dt><dd>Dashboard test</dd></div>
            <div><dt>Knowledge scope</dt><dd>Workspace sources</dd></div>
            <div><dt>Channel</dt><dd>dashboard test</dd></div>
          </dl>
        </aside>
      </div>
    </section>
  );
}

function ChatbotMessage({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <article className="messageBubble message-user">
        <div className="messageHeader"><span>User</span></div>
        <p>{message.content}</p>
      </article>
    );
  }

  return (
    <article className="messageBubble message-assistant">
      <div className="messageHeader">
        <span>Assistant</span>
        <ConversationStatusBadge status={message.answerState} answerState />
      </div>
      <p>{message.content}</p>
      {message.fallbackUsed ? (
        <p className="chatbotFallbackNotice">The assistant used the safe fallback path because indexed context was insufficient or unavailable.</p>
      ) : null}
      <ChatbotCitationList citations={message.citations} />
      <dl className="chatbotAnswerMeta">
        <div><dt>Retrieved chunks</dt><dd>{message.retrievedChunkCount}</dd></div>
        <div><dt>Latency</dt><dd>{message.latencyMs} ms</dd></div>
        <div><dt>Provider</dt><dd>{message.providerKey}</dd></div>
        <div><dt>Model</dt><dd>{message.modelKey}</dd></div>
      </dl>
    </article>
  );
}

function ChatbotCitationList({ citations }: { citations: RAGCitation[] }) {
  if (citations.length === 0) return null;

  return (
    <div className="citationList" aria-label="Assistant citations">
      {citations.map((citation) => (
        <article className="citationCard" key={`${citation.document_version_id}-${citation.chunk_id}-${citation.citation_index}`}>
          <div>
            <strong>[{citation.citation_index}] {citation.source_title}</strong>
            <p>{citation.quoted_text || "Citation text was not stored."}</p>
          </div>
          <dl>
            <div><dt>Type</dt><dd>{citation.source_type}</dd></div>
            {citation.page_number !== null ? <div><dt>Page</dt><dd>{citation.page_number}</dd></div> : null}
            {citation.section_title ? <div><dt>Section</dt><dd>{citation.section_title}</dd></div> : null}
            {citation.similarity_score !== null ? <div><dt>Similarity</dt><dd>{citation.similarity_score.toFixed(3)}</dd></div> : null}
          </dl>
        </article>
      ))}
    </div>
  );
}

function assistantMessageFromResponse(data: RAGAnswerResponse): ChatMessage {
  return {
    id: data.assistant_message_id,
    role: "assistant",
    content: data.answer,
    answerState: data.answer_state,
    fallbackUsed: data.fallback_used,
    citations: data.citations,
    retrievedChunkCount: data.retrieved_chunk_count,
    latencyMs: data.latency_ms,
    providerKey: data.provider_key,
    modelKey: data.model_key,
  };
}

function messageForChatbotError(error: unknown) {
  if (isDashboardApiError(error)) {
    if (error.kind === "validation") return "Enter a question between 1 and 4000 characters.";
    if (error.kind === "forbidden") return "This user cannot ask questions in the selected workspace.";
    if (error.kind === "not_found") return "The workspace or conversation was not found for this organisation.";
    if (error.kind === "network") return "The API could not be reached. Check that the backend is running.";
    if (error.kind === "server") return "The answer service returned an operational error. The conversation may contain a failed assistant message for review.";
  }
  return "The chatbot request could not be completed.";
}


