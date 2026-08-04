import { FileWarning, Layers } from "lucide-react";
import Link from "next/link";

import type { ReviewItem } from "../../lib/api/types";
import { formatDate, formatEnum } from "../conversations/conversation-list";
import { ConversationStatusBadge } from "../conversations/conversation-status-badge";
import { ReviewStatusBadge } from "./review-status-badge";

export type ReviewPriorityLevel = "high" | "medium" | "low";

export type ReviewPriority = {
  level: ReviewPriorityLevel;
  label: string;
  reason: string;
};

type ReviewListProps = {
  items: ReviewItem[];
  assistantId: string;
  assistantLabel?: string;
};

export function ReviewList({ items, assistantId, assistantLabel }: ReviewListProps) {
  return (
    <div className="reviewList" role="list" aria-label="Knowledge gap review results">
      {items.map((item) => (
        <ReviewCard key={item.assistant_message_id} item={item} assistantId={assistantId} assistantLabel={assistantLabel} />
      ))}
    </div>
  );
}

export function ReviewCard({ item, assistantId, assistantLabel }: { item: ReviewItem; assistantId: string; assistantLabel?: string }) {
  const priority = deriveReviewPriority(item);
  const question = item.user_question || "Question unavailable";
  const href = `/review/unanswered/${item.assistant_message_id}?assistant=${item.assistant_id || assistantId}`;

  return (
    <article className="reviewCard" role="listitem">
      <Link
        className="reviewCardLink"
        href={href}
        aria-label={`${question}. ${formatEnum(item.answer_state)} answer, ${formatEnum(item.review_status)} review status. ${priority.label}. ${item.citation_count} citation${item.citation_count === 1 ? "" : "s"}. Created ${formatDate(item.created_at)}.`}
      >
        <div className="reviewCardTop">
          <h3>{question}</h3>
          <span className={`reviewPriorityBadge tone-${priority.level}`}>{priority.label}</span>
        </div>
        <p className="reviewCardPreview">{preview(item.assistant_answer)}</p>
        <div className="reviewCardBadges">
          <ConversationStatusBadge status={item.answer_state} answerState />
          <ReviewStatusBadge status={item.review_status} />
          {item.citation_count === 0 ? (
            <span className="reviewKnowledgeIndicator tone-warning"><FileWarning size={13} aria-hidden="true" />No sources retrieved</span>
          ) : (
            <span className="reviewKnowledgeIndicator tone-neutral"><Layers size={13} aria-hidden="true" />{item.citation_count} source{item.citation_count === 1 ? "" : "s"}</span>
          )}
        </div>
        <div className="reviewCardMeta" aria-hidden="true">
          {assistantLabel ? <span>{assistantLabel}</span> : null}
          <span>{formatEnum(item.channel)}</span>
          <span>{formatDate(item.created_at)}</span>
          <span>{item.latency_ms === null ? "No latency sample" : `${item.latency_ms} ms`}</span>
        </div>
      </Link>
    </article>
  );
}

export function deriveReviewPriority(item: ReviewItem): ReviewPriority {
  if (item.review_status !== "open") {
    return { level: "low", label: "Resolved", reason: `Already ${formatEnum(item.review_status)}.` };
  }
  if (item.answer_state === "failed") {
    return { level: "high", label: "High priority", reason: "Failed answer and still open." };
  }
  const ageDays = daysSince(item.created_at);
  if ((item.answer_state === "fallback" || item.answer_state === "low_confidence") && ageDays >= 3) {
    return { level: "high", label: "High priority", reason: `Open for ${ageDays} day${ageDays === 1 ? "" : "s"} without review.` };
  }
  return { level: "medium", label: "Needs review", reason: "Open and awaiting review." };
}

function daysSince(value: string) {
  return Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000);
}

function preview(value: string, maxChars = 180) {
  const compact = " ".concat(value).trim().replace(/\s+/g, " ");
  if (compact.length <= maxChars) return compact;
  return `${compact.slice(0, maxChars - 1).trim()}...`;
}
