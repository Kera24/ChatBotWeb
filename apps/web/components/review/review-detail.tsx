import Link from "next/link";

import { CitationList } from "../conversations/citation-list";
import { ConversationStatusBadge } from "../conversations/conversation-status-badge";
import { formatDate, formatEnum } from "../conversations/conversation-list";
import { MessageThread } from "../conversations/message-thread";
import { TechnicalDetails } from "../conversations/technical-details";
import type { ReviewItemDetail } from "../../lib/api/types";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { ReviewDecisionForm } from "./review-decision-form";
import { ReviewStatusBadge } from "./review-status-badge";

type ReviewDetailProps = {
  detail: ReviewItemDetail;
  session: DevelopmentDashboardSession;
  canUpdate: boolean;
};

export function ReviewDetail({ detail, session, canUpdate }: ReviewDetailProps) {
  const item = detail.item;
  const assistantMessage = detail.conversation_context.find((message) => message.id === item.assistant_message_id);
  return (
    <section className="reviewDetailPage" aria-labelledby="review-detail-title">
      <Link className="backLink" href="/review/unanswered">Back to review queue</Link>
      <div className="detailHero reviewDetailHero">
        <div>
          <p className="eyebrow">Knowledge gap review</p>
          <h2 id="review-detail-title">{item.user_question || "Question unavailable"}</h2>
          <p>Separate the user question, assistant response, signal, and reviewer decision before changing knowledge content.</p>
        </div>
        <div className="reviewHeroBadges">
          <ConversationStatusBadge status={item.answer_state} answerState />
          <ReviewStatusBadge status={item.review_status} />
        </div>
      </div>

      <div className="reviewDetailGrid">
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
        <section className="reviewStoryPanel" aria-labelledby="flagged-title">
          <p className="sectionKicker">Why it was flagged</p>
          <h3 id="flagged-title">Signal</h3>
          <dl className="detailMeta compactMeta">
            <div><dt>Answer state</dt><dd><ConversationStatusBadge status={item.answer_state} answerState /></dd></div>
            <div><dt>Error code</dt><dd>{item.error_code || "None"}</dd></div>
            <div><dt>Channel</dt><dd>{formatEnum(item.channel)}</dd></div>
            <div><dt>Created</dt><dd>{formatDate(item.created_at)}</dd></div>
            <div><dt>Citations</dt><dd>{item.citation_count}</dd></div>
          </dl>
        </section>
        <ReviewDecisionForm session={session} item={item} canUpdate={canUpdate} />
      </div>

      <section className="reviewStoryPanel" aria-labelledby="citations-title">
        <p className="sectionKicker">Sources</p>
        <h3 id="citations-title">Citations attached to this answer</h3>
        <CitationList citations={item.citations} />
        {item.citations.length === 0 ? <p>No citations were attached to this flagged answer.</p> : null}
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
        <MessageThread messages={detail.conversation_context} />
      </section>
    </section>
  );
}
