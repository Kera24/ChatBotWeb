"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Bot, Clipboard, ClipboardCheck, ExternalLink, User } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import type { ConversationCitation, ConversationMessage } from "../../lib/api/types";
import { CitationChipList, CitationDrawer } from "./citation-panel";
import { ConversationStatusBadge } from "./conversation-status-badge";
import { TechnicalDetails } from "./technical-details";

const FLAGGED_STATES = new Set(["fallback", "low_confidence", "failed"]);

type ConversationTranscriptProps = {
  messages: ConversationMessage[];
  assistantId: string;
};

export function ConversationTranscript({ messages, assistantId }: ConversationTranscriptProps) {
  const reduceMotion = useReducedMotion();
  const [selectedCitation, setSelectedCitation] = useState<ConversationCitation | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

  async function copyAnswer(message: ConversationMessage) {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopiedMessageId(message.id);
      window.setTimeout(() => setCopiedMessageId((current) => (current === message.id ? null : current)), 2000);
    } catch {
      // Clipboard access can be denied by the browser; the answer remains visible for manual copy.
    }
  }

  if (messages.length === 0) {
    return (
      <div className="premiumTranscript conversationTranscript" role="log" aria-label="Conversation messages">
        <div className="chatEmptyState">
          <h3>No messages recorded</h3>
          <p>This conversation does not have any messages yet.</p>
        </div>
      </div>
    );
  }

  return (
    <section className="premiumTranscript conversationTranscript" role="log" aria-label="Conversation messages">
      <AnimatePresence initial={false}>
        {messages.map((message, index) => (
          <TranscriptBubble
            key={message.id}
            message={message}
            index={index}
            assistantId={assistantId}
            copied={copiedMessageId === message.id}
            onCopy={copyAnswer}
            onSelectCitation={setSelectedCitation}
            reduceMotion={Boolean(reduceMotion)}
          />
        ))}
      </AnimatePresence>
      <CitationDrawer citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
    </section>
  );
}

function TranscriptBubble({
  message,
  index,
  assistantId,
  copied,
  onCopy,
  onSelectCitation,
  reduceMotion,
}: {
  message: ConversationMessage;
  index: number;
  assistantId: string;
  copied: boolean;
  onCopy: (message: ConversationMessage) => void;
  onSelectCitation: (citation: ConversationCitation) => void;
  reduceMotion: boolean;
}) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const isFlagged = isAssistant && Boolean(message.answer_state) && FLAGGED_STATES.has(message.answer_state as string);
  const motionProps = reduceMotion
    ? { initial: false, animate: {} }
    : { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -8 }, transition: { delay: Math.min(index, 8) * 0.03 } };

  return (
    <motion.article className={`chatBubble ${isUser ? "userBubble" : "assistantBubble"}`} {...motionProps}>
      <div className="chatBubbleHeader">
        <span>
          {isUser ? <User size={15} aria-hidden="true" /> : <Bot size={15} aria-hidden="true" />}
          {roleLabel(message.role)}
        </span>
        {message.answer_state ? <ConversationStatusBadge status={message.answer_state} answerState /> : null}
      </div>
      <p>{message.content}</p>

      {isAssistant ? (
        <>
          <CitationChipList citations={message.citations} onSelectCitation={onSelectCitation} />
          <div className="conversationTranscriptFooter">
            {isFlagged ? (
              <Link className="chatIconAction" href={`/review/unanswered/${message.id}?assistant=${assistantId}`}>
                <ExternalLink size={14} aria-hidden="true" />
                Open review record
              </Link>
            ) : null}
            <button className="chatIconAction" type="button" onClick={() => onCopy(message)} aria-label="Copy assistant answer">
              {copied ? <ClipboardCheck size={16} aria-hidden="true" /> : <Clipboard size={16} aria-hidden="true" />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <TechnicalDetails message={message} />
        </>
      ) : null}
    </motion.article>
  );
}

function roleLabel(role: string) {
  if (role === "assistant") return "Assistant";
  if (role === "user") return "User";
  return role.replace(/_/g, " ");
}
