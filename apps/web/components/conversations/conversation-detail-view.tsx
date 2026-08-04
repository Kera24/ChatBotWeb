"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import type { ConversationDetail } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { assistantLifecycle } from "../assistants/assistant-management";
import { ConversationArchivedNotice, ConversationDetailHeader } from "./conversation-header";
import { ConversationQualityPanel, summarizeConversationQuality } from "./conversation-quality-panel";
import { ConversationTranscript } from "./conversation-transcript";

export function ConversationDetailView({ conversation, assistant }: { conversation: ConversationDetail; assistant: WidgetDetail }) {
  const reduceMotion = useReducedMotion();
  const lifecycle = assistantLifecycle(assistant);
  const summary = summarizeConversationQuality(conversation);
  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } };

  return (
    <motion.section className="conversationDetailPage premiumConversationDetailPage" aria-labelledby="detail-title" {...pageMotion}>
      <Link className="backLink premiumBackLink" href={`/conversations?assistant=${assistant.id}`}>
        <ArrowLeft size={15} aria-hidden="true" />
        Back to conversations
      </Link>

      <ConversationDetailHeader conversation={conversation} assistant={assistant} />
      {lifecycle === "Archived" ? <ConversationArchivedNotice /> : null}

      <div className="conversationDetailGrid">
        <ConversationTranscript messages={conversation.messages} assistantId={assistant.id} />
        <ConversationQualityPanel summary={summary} assistantId={assistant.id} />
      </div>
    </motion.section>
  );
}
