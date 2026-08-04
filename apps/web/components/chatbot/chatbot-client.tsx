"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AlertTriangle, BarChart3, Bot, CheckCircle2, Clipboard, ClipboardCheck, Database, ExternalLink, FileText, Info, Loader2, MessageSquarePlus, Send, ShieldCheck, Sparkles, X, XCircle } from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

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

type ChatbotClientProps = { session: DevelopmentDashboardSession; assistantId: string; missingAssistant?: boolean };

export function ChatbotClient({ session, assistantId, missingAssistant = false }: ChatbotClientProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [composer, setComposer] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<RAGCitation | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const sequence = useRef(0);
  const reduceMotion = useReducedMotion();

  const assistantAnswers = messages.filter((message) => message.role === "assistant");
  const canSend = composer.trim().length > 0 && !pending && !missingAssistant;
  const conversationLabel = useMemo(() => conversationId ? `Conversation ${conversationId.slice(0, 8)}` : "New test conversation", [conversationId]);
  const assistantContextLabel = assistantId || "No assistant selected";

  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const query = composer.trim();
    if (!query || pending || missingAssistant) return;

    const userMessage: ChatMessage = { id: `local-user-${++sequence.current}`, role: "user", content: query };
    setMessages((current) => [...current, userMessage]);
    setComposer("");
    setPending(true);
    setError(null);

    try {
      const response = await answerChatbotQuestion(session, { query, conversationId, assistantId });
      setConversationId(response.data.conversation_id);
      setMessages((current) => [...current, assistantMessageFromResponse(response.data)]);
    } catch (caught) {
      setError(messageForChatbotError(caught));
    } finally {
      setPending(false);
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  function startNewConversation() {
    if (pending) return;
    setMessages([]);
    setConversationId(null);
    setError(null);
    setComposer("");
    setSelectedCitation(null);
    setCopiedMessageId(null);
  }

  async function copyAnswer(message: Extract<ChatMessage, { role: "assistant" }>) {
    try {
      await navigator.clipboard?.writeText(message.content);
      setCopiedMessageId(message.id);
      window.setTimeout(() => setCopiedMessageId(null), 1600);
    } catch {
      setError("The answer could not be copied in this browser session.");
    }
  }

  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.35 } };

  return (
    <motion.section className="chatbotPage premiumChatPage" aria-labelledby="chatbot-title" {...pageMotion}>
      <ChatHeader assistantId={assistantId} assistantLabel={assistantContextLabel} missingAssistant={missingAssistant} answerCount={assistantAnswers.length} />

      {missingAssistant ? <div className="chatAlert danger" role="alert"><XCircle size={18} aria-hidden="true" /><div><h2>Select an assistant</h2><p>Assistant context is required before testing retrieval. Choose an assistant from the switcher or return to My AI Assistants.</p></div></div> : null}

      <div className="premiumChatLayout">
        <section className="premiumChatPanel" aria-label="Assistant chat test">
          <div className="chatThreadToolbar">
            <div><span>Current thread</span><strong>{conversationLabel}</strong></div>
            <div className="chatThreadActions"><Link className="chatButton ghost" href={`/conversations?assistant=${assistantId}`}><ExternalLink size={15} aria-hidden="true" />History</Link><button type="button" className="chatButton ghost" onClick={startNewConversation} disabled={pending || messages.length === 0}><MessageSquarePlus size={15} aria-hidden="true" />New conversation</button></div>
          </div>

          <div className="premiumTranscript" role="log" aria-live="polite" aria-label="Chat transcript">
            {messages.length === 0 ? <ChatEmptyState assistantId={assistantContextLabel} /> : null}
            <AnimatePresence initial={false}>{messages.map((message) => <MessageBubble key={message.id} message={message} copied={copiedMessageId === message.id} onCopy={copyAnswer} onSelectCitation={setSelectedCitation} />)}</AnimatePresence>
            {pending ? <TypingIndicator /> : null}
          </div>

          {error ? <div className="chatAlert danger inline" role="alert"><AlertTriangle size={17} aria-hidden="true" />{error}</div> : null}

          <ChatComposer value={composer} setValue={setComposer} pending={pending} canSend={canSend} onSubmit={submit} onKeyDown={handleComposerKeyDown} missingAssistant={missingAssistant} />
        </section>

        <ChatContextPanel assistantId={assistantId} conversationId={conversationId} answerCount={assistantAnswers.length} pending={pending} />
      </div>

      <CitationDrawer citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
    </motion.section>
  );
}

function ChatHeader({ assistantId, assistantLabel, missingAssistant, answerCount }: { assistantId: string; assistantLabel: string; missingAssistant: boolean; answerCount: number }) {
  return <header className="chatControlHeader"><div className="chatHeaderIdentity"><div className="chatAssistantAvatar" aria-hidden="true"><Bot size={26} /></div><div><p className="chatEyebrow"><Sparkles size={14} aria-hidden="true" />Conversa Chat Playground</p><h2 id="chatbot-title">Chat Playground</h2><p>Test assistant-scoped grounded answers, citations, fallback behavior, and operational metadata before publishing changes.</p><div className="chatContextBadges" aria-label="Selected assistant context"><span><ShieldCheck size={14} aria-hidden="true" />Assistant scoped</span><span>{missingAssistant ? "No assistant selected" : `Assistant ${assistantLabel}`}</span><span>{answerCount} answer{answerCount === 1 ? "" : "s"} in this test</span></div></div></div><div className="chatHeaderActions"><Link className="chatButton secondary" href={assistantId ? `/knowledge?assistant=${assistantId}` : "/dashboard"}><Database size={16} aria-hidden="true" />Knowledge</Link><Link className="chatButton secondary" href={assistantId ? `/widgets?assistant=${assistantId}` : "/dashboard"}><Bot size={16} aria-hidden="true" />Widget</Link></div></header>;
}

function ChatEmptyState({ assistantId }: { assistantId: string }) {
  return <div className="chatEmptyState"><div className="chatEmptyAvatar" aria-hidden="true"><Bot size={32} /><span /></div><h3>Start a grounded test conversation</h3><p>Ask a real customer question for assistant {assistantId}. The response will reuse the authenticated RAG endpoint and persist as a dashboard test conversation.</p><div className="chatPromptExamples" aria-label="Example test prompts"><span>What policy answers should this assistant know?</span><span>Which sources support the answer?</span><span>What should happen when knowledge is missing?</span></div></div>;
}

function ChatComposer({ value, setValue, pending, canSend, onSubmit, onKeyDown, missingAssistant }: { value: string; setValue: (value: string) => void; pending: boolean; canSend: boolean; onSubmit: (event?: FormEvent<HTMLFormElement>) => void | Promise<void>; onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void; missingAssistant: boolean }) {
  return <form className="premiumComposer" onSubmit={(event) => void onSubmit(event)}><label htmlFor="chatbot-message">Message</label><div className="composerDock"><textarea id="chatbot-message" value={value} maxLength={4000} rows={3} placeholder={missingAssistant ? "Select an assistant before testing" : "Ask a question about this assistant's indexed knowledge"} onChange={(event) => setValue(event.target.value)} onKeyDown={onKeyDown} disabled={pending || missingAssistant} /><div className="composerFooter"><span>Enter to send - Shift+Enter for a new line - {value.length}/4000</span><button className="chatButton primary" type="submit" disabled={!canSend}>{pending ? <Loader2 className="spinIcon" size={16} aria-hidden="true" /> : <Send size={16} aria-hidden="true" />}{pending ? "Sending" : "Send"}</button></div></div></form>;
}

function MessageBubble({ message, copied, onCopy, onSelectCitation }: { message: ChatMessage; copied: boolean; onCopy: (message: Extract<ChatMessage, { role: "assistant" }>) => void; onSelectCitation: (citation: RAGCitation) => void }) {
  if (message.role === "user") {
    return <motion.article className="chatBubble userBubble" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}><div className="chatBubbleHeader"><span>You</span></div><p>{message.content}</p></motion.article>;
  }
  return <motion.article className="chatBubble assistantBubble" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}><div className="chatBubbleHeader"><span><Bot size={15} aria-hidden="true" />Assistant</span><AnswerStateBadge state={message.answerState} fallbackUsed={message.fallbackUsed} /></div><p>{message.content}</p>{message.fallbackUsed ? <div className="chatQualityNotice"><Info size={15} aria-hidden="true" />The assistant used the safe fallback path because indexed context was insufficient or unavailable.</div> : null}<CitationList citations={message.citations} onSelectCitation={onSelectCitation} /><div className="chatAnswerFooter"><dl className="chatAnswerMeta"><div><dt>Retrieved</dt><dd>{message.retrievedChunkCount} chunks</dd></div><div><dt>Latency</dt><dd>{message.latencyMs} ms</dd></div><div><dt>Provider</dt><dd>{message.providerKey}</dd></div><div><dt>Model</dt><dd>{message.modelKey}</dd></div></dl><button className="chatIconAction" type="button" onClick={() => void onCopy(message)} aria-label="Copy assistant answer">{copied ? <ClipboardCheck size={16} aria-hidden="true" /> : <Clipboard size={16} aria-hidden="true" />}{copied ? "Copied" : "Copy"}</button></div></motion.article>;
}

function CitationList({ citations, onSelectCitation }: { citations: RAGCitation[]; onSelectCitation: (citation: RAGCitation) => void }) {
  if (citations.length === 0) return <div className="citationEmpty"><Info size={14} aria-hidden="true" />No citations were returned for this answer.</div>;
  return <div className="premiumCitationList" aria-label="Assistant citations"><div className="citationListHeader"><strong>Sources</strong><span>{citations.length} citation{citations.length === 1 ? "" : "s"}</span></div>{citations.map((citation) => <button className="citationChip" type="button" key={`${citation.document_version_id}-${citation.chunk_id}-${citation.citation_index}`} onClick={() => onSelectCitation(citation)} aria-label={`Open citation ${citation.citation_index}: ${citation.source_title}`}><span>[{citation.citation_index}]</span><strong>{citation.source_title}</strong><small>{citation.source_type}{citation.page_number !== null ? ` - page ${citation.page_number}` : ""}</small></button>)}</div>;
}

function CitationDrawer({ citation, onClose }: { citation: RAGCitation | null; onClose: () => void }) {
  return <AnimatePresence>{citation ? <motion.div className="citationDrawerBackdrop" role="presentation" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}><motion.aside className="citationDrawer" role="dialog" aria-modal="true" aria-labelledby="citation-drawer-title" initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 24 }}><div className="citationDrawerHeader"><div><p>Source reference</p><h2 id="citation-drawer-title">[{citation.citation_index}] {citation.source_title}</h2></div><button className="chatIconButton" type="button" onClick={onClose} aria-label="Close citation details"><X size={18} aria-hidden="true" /></button></div><blockquote>{citation.quoted_text || "Citation text was not stored by the current answer contract."}</blockquote><dl className="citationFacts"><div><dt>Document</dt><dd>{citation.document_id}</dd></div><div><dt>Version</dt><dd>{citation.document_version_id}</dd></div><div><dt>Chunk</dt><dd>{citation.chunk_id}</dd></div><div><dt>Type</dt><dd>{citation.source_type}</dd></div>{citation.page_number !== null ? <div><dt>Page</dt><dd>{citation.page_number}</dd></div> : null}{citation.section_title ? <div><dt>Section</dt><dd>{citation.section_title}</dd></div> : null}{citation.similarity_score !== null ? <div><dt>Similarity</dt><dd>{citation.similarity_score.toFixed(3)}</dd></div> : null}</dl></motion.aside></motion.div> : null}</AnimatePresence>;
}

function ChatContextPanel({ assistantId, conversationId, answerCount, pending }: { assistantId: string; conversationId: string | null; answerCount: number; pending: boolean }) {
  return <aside className="premiumChatSidePanel" aria-label="Chat playground context"><section><p className="chatSideKicker">Assistant context</p><h2>Testing workspace</h2><dl className="chatSideFacts"><div><dt>Mode</dt><dd>Dashboard test</dd></div><div><dt>Assistant</dt><dd>{assistantId || "Required"}</dd></div><div><dt>Conversation</dt><dd>{conversationId ? conversationId.slice(0, 8) : "New"}</dd></div><div><dt>Status</dt><dd>{pending ? "Generating" : "Ready"}</dd></div></dl></section><section><p className="chatSideKicker">Operational links</p><div className="chatSideLinks"><Link href={assistantId ? `/knowledge?assistant=${assistantId}` : "/dashboard"}><Database size={15} aria-hidden="true" />Manage knowledge</Link><Link href={`/conversations?assistant=${assistantId}&channel=dashboard_test`}><FileText size={15} aria-hidden="true" />Review conversations</Link><Link href={assistantId ? `/widgets?assistant=${assistantId}` : "/dashboard"}><Bot size={15} aria-hidden="true" />Configure widget</Link><Link href={`/analytics?assistant=${assistantId}`}><BarChart3 size={15} aria-hidden="true" />View analytics</Link></div></section><section className="chatReadinessCard"><CheckCircle2 size={18} aria-hidden="true" /><div><strong>{answerCount} tested answer{answerCount === 1 ? "" : "s"}</strong><span>Responses are persisted through the existing dashboard_test channel.</span></div></section></aside>;
}

function AnswerStateBadge({ state, fallbackUsed }: { state: string; fallbackUsed: boolean }) {
  const tone = fallbackUsed || state === "fallback" ? "fallback" : state === "answered" ? "answered" : state === "failed" ? "failed" : state === "low_confidence" ? "low" : state === "blocked" ? "blocked" : "neutral";
  const Icon = tone === "answered" ? CheckCircle2 : tone === "failed" ? XCircle : tone === "fallback" || tone === "low" ? AlertTriangle : Info;
  return <span className={`answerStateBadge state-${tone}`} aria-label={`Answer state: ${state.replaceAll("_", " ")}`}><Icon size={13} aria-hidden="true" />{state.replaceAll("_", " ")}</span>;
}

function TypingIndicator() {
  return <motion.article className="chatBubble assistantBubble typingBubble" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} role="status"><div className="chatBubbleHeader"><span><Bot size={15} aria-hidden="true" />Assistant</span><ConversationStatusBadge status="pending" answerState /></div><div className="typingDots" aria-label="Generating answer"><span /><span /><span /></div><p>Searching assistant knowledge and preparing a grounded answer...</p></motion.article>;
}

function assistantMessageFromResponse(data: RAGAnswerResponse): ChatMessage {
  return { id: data.assistant_message_id, role: "assistant", content: data.answer, answerState: data.answer_state, fallbackUsed: data.fallback_used, citations: data.citations, retrievedChunkCount: data.retrieved_chunk_count, latencyMs: data.latency_ms, providerKey: data.provider_key, modelKey: data.model_key };
}

function messageForChatbotError(error: unknown) {
  if (isDashboardApiError(error)) {
    if (error.kind === "validation") return "Enter a question between 1 and 4000 characters.";
    if (error.kind === "forbidden") return "This user cannot ask questions in the selected workspace.";
    if (error.kind === "not_found") return "The workspace, assistant, or conversation was not found for this organisation.";
    if (error.kind === "network") return "The API could not be reached. Check that the backend is running.";
    if (error.kind === "server") return "The answer service returned an operational error. The conversation may contain a failed assistant message for review.";
  }
  return "The chatbot request could not be completed.";
}
