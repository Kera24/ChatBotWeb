"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { CitationChipList, CitationDrawer } from "../conversations/citation-panel";
import { ConversationTranscript } from "../conversations/conversation-transcript";
import { TechnicalDetails } from "../conversations/technical-details";
import type { ConversationCitation } from "../../lib/api/types";
import type { ReviewItemDetail } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { assistantLifecycle } from "../assistants/assistant-management";
import { KnowledgeGapPanel } from "./knowledge-gap-panel";
import { ReviewArchivedNotice, ReviewDetailHeader } from "./review-header";
import { ReviewDecisionForm } from "./review-decision-form";
import { ReviewQualityPanel } from "./review-quality-panel";

export function ReviewDetailView({
  detail,
  assistant,
  session,
  canUpdate,
}: {
  detail: ReviewItemDetail;
  assistant: WidgetDetail;
  session: DevelopmentDashboardSession;
  canUpdate: boolean;
}) {
  const reduceMotion = useReducedMotion();
  const [selectedCitation, setSelectedCitation] = useState<ConversationCitation | null>(null);
  const item = detail.item;
  const assistantMessage = detail.conversation_context.find((message) => message.id === item.assistant_message_id);
  const lifecycle = assistantLifecycle(assistant);
  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } };

  return (
    <motion.section className="reviewDetailPage premiumReviewDetailPage" aria-labelledby="review-detail-title" {...pageMotion}>
      <Link className="backLink premiumBackLink" href={`/review/unanswered?assistant=${assistant.id}`}>
        <ArrowLeft size={15} aria-hidden="true" />
        Back to review queue
      </Link>

      <ReviewDetailHeader item={item} assistant={assistant} />
      {lifecycle === "Archived" ? <ReviewArchivedNotice /> : null}

      <div className="reviewDetailGrid premiumReviewDetailGrid">
        <section className="reviewStoryPanel" aria-labelledby="asked-title">
          <p className="sectionKicker">What the user asked</p>
          <h3 id="asked-title">Original question</h3>
          <p>{item.user_question || "No preceding user question was found."}</p>
        </section>
        <section className="reviewStoryPanel" aria-labelledby="answered-title">
          <p className="sectionKicker">What the assistant answered</p>
          <h3 id="answered-title">Flagged response</h3>
          <p>{item.assistant_answer}</p>
        </section>
        <ReviewQualityPanel item={item} assistant={assistant} workspaceId={session.workspaceId} />
        <ReviewDecisionForm session={session} item={item} canUpdate={canUpdate} />
      </div>

      <KnowledgeGapPanel item={item} />

      <section className="reviewStoryPanel" aria-labelledby="citations-title">
        <p className="sectionKicker">Sources</p>
        <h3 id="citations-title">Citations attached to this answer</h3>
        <CitationChipList citations={item.citations} onSelectCitation={setSelectedCitation} />
      </section>

      {assistantMessage ? (
        <section className="reviewStoryPanel" aria-labelledby="technical-title">
          <p className="sectionKicker">Safe technical details</p>
          <h3 id="technical-title">Execution metadata</h3>
          <TechnicalDetails message={assistantMessage} />
        </section>
      ) : null}

      <section className="reviewStoryPanel" aria-labelledby="context-title">
        <p className="sectionKicker">Conversation context</p>
        <h3 id="context-title">Nearby messages</h3>
        <ConversationTranscript messages={detail.conversation_context} assistantId={assistant.id} />
      </section>

      <CitationDrawer citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
    </motion.section>
  );
}
