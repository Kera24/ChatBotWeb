import Link from "next/link";

import { ConversationStatusBadge } from "../conversations/conversation-status-badge";
import { formatDate, formatEnum } from "../conversations/conversation-list";
import type { ReviewItem } from "../../lib/api/types";
import { ReviewStatusBadge } from "./review-status-badge";

type ReviewListProps = {
  items: ReviewItem[];
};

export function ReviewList({ items }: ReviewListProps) {
  return (
    <div className="reviewList" aria-label="Knowledge gap review results">
      {items.map((item) => (
        <article className={`reviewRow review-answer-${item.answer_state}`} key={item.assistant_message_id}>
          <div className="reviewRowMain">
            <div className="conversationRowTitleLine">
              <h2>
                <Link href={`/review/unanswered/${item.assistant_message_id}`}>
                  {item.user_question || "Question unavailable"}
                </Link>
              </h2>
              <ConversationStatusBadge status={item.answer_state} answerState />
              <ReviewStatusBadge status={item.review_status} />
            </div>
            <p>{preview(item.assistant_answer)}</p>
          </div>
          <dl className="conversationFacts">
            <div>
              <dt>Channel</dt>
              <dd>{formatEnum(item.channel)}</dd>
            </div>
            <div>
              <dt>Citations</dt>
              <dd>{item.citation_count}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDate(item.created_at)}</dd>
            </div>
            <div>
              <dt>Latency</dt>
              <dd>{item.latency_ms === null ? "None" : `${item.latency_ms} ms`}</dd>
            </div>
            <div>
              <dt>Cost</dt>
              <dd>{item.estimated_cost === null ? "None" : item.estimated_cost}</dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}

function preview(value: string, maxChars = 180) {
  const compact = " ".concat(value).trim().replace(/\s+/g, " ");
  if (compact.length <= maxChars) return compact;
  return `${compact.slice(0, maxChars - 1).trim()}...`;
}
