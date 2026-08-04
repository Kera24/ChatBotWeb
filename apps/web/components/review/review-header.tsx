import { Activity, BarChart3, Database, MessageSquare, ShieldAlert } from "lucide-react";
import Link from "next/link";

import type { ReviewItem } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";
import { assistantLifecycle, AssistantStatusBadge } from "../assistants/assistant-management";
import { ConversationStatusBadge } from "../conversations/conversation-status-badge";
import { ReviewStatusBadge } from "./review-status-badge";

export function ReviewQueueHeader({
  assistant,
  pending,
  resolved,
  totalInFilter,
  periodLabel,
}: {
  assistant: WidgetDetail;
  pending: number;
  resolved: number;
  totalInFilter: number;
  periodLabel: string;
}) {
  const lifecycle = assistantLifecycle(assistant);
  return (
    <header className="premiumReviewHero">
      <div className="reviewHeroMain">
        <div>
          <p className="eyebrow">Knowledge gaps</p>
          <h2 id="review-title">Review Queue</h2>
          <p>Review {assistant.display_name}&rsquo;s fallback, failed, and low-confidence answers so missing knowledge becomes visible.</p>
          <div className="reviewHeroMeta" aria-label="Assistant and review summary">
            <AssistantStatusBadge status={lifecycle} />
            <span>{pending} pending</span>
            <span>{resolved} resolved</span>
            <span>{totalInFilter} in current filter</span>
            <span>{periodLabel}</span>
          </div>
        </div>
      </div>
      <ReviewQuickLinks assistantId={assistant.id} />
    </header>
  );
}

export function ReviewDetailHeader({ item, assistant }: { item: ReviewItem; assistant: WidgetDetail }) {
  return (
    <header className="premiumReviewDetailHero">
      <div className="reviewHeroMain">
        <div>
          <p className="eyebrow">Knowledge gap review</p>
          <h2 id="review-detail-title">{item.user_question || "Question unavailable"}</h2>
          <p>Separate the user question, assistant response, signal, and reviewer decision before changing knowledge content.</p>
          <div className="reviewHeroMeta" aria-label="Review item state summary">
            <ConversationStatusBadge status={item.answer_state} answerState />
            <ReviewStatusBadge status={item.review_status} />
            <span>Assistant {assistant.display_name}</span>
          </div>
        </div>
      </div>
      <ReviewQuickLinks assistantId={assistant.id} />
    </header>
  );
}

function ReviewQuickLinks({ assistantId }: { assistantId: string }) {
  return (
    <nav className="reviewQuickLinks" aria-label="Assistant quick links">
      <Link href={`/knowledge?assistant=${assistantId}`}><Database size={15} aria-hidden="true" />Knowledge</Link>
      <Link href={`/chatbot?assistant=${assistantId}`}><MessageSquare size={15} aria-hidden="true" />Chat Playground</Link>
      <Link href={`/analytics?assistant=${assistantId}`}><BarChart3 size={15} aria-hidden="true" />Analytics</Link>
      <Link href={`/conversations?assistant=${assistantId}`}><Activity size={15} aria-hidden="true" />Conversations</Link>
    </nav>
  );
}

export function ReviewArchivedNotice() {
  return (
    <p className="reviewArchivedNotice" role="status">
      <ShieldAlert size={15} aria-hidden="true" />
      This assistant is archived. Review history remains available for reference.
    </p>
  );
}
