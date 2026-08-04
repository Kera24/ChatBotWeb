import { AlertTriangle, CheckCircle2, FileWarning, Info, XCircle, type LucideIcon } from "lucide-react";

import type { ReviewItem } from "../../lib/api/types";

type GuidanceTone = "danger" | "warning" | "info" | "success";

type Guidance = {
  id: string;
  tone: GuidanceTone;
  title: string;
  detail: string;
};

const TONE_ICON: Record<GuidanceTone, LucideIcon> = { danger: XCircle, warning: AlertTriangle, info: Info, success: CheckCircle2 };

export function deriveKnowledgeGuidance(item: ReviewItem): Guidance[] {
  const guidance: Guidance[] = [];

  if (item.citation_count === 0) {
    guidance.push({
      id: "missing-citations",
      tone: "danger",
      title: "Missing citations",
      detail: "No source documents were retrieved for this answer. This usually means the knowledge base has no relevant content.",
    });
  } else {
    guidance.push({
      id: "has-citations",
      tone: "info",
      title: "Sources were retrieved",
      detail: `${item.citation_count} citation${item.citation_count === 1 ? "" : "s"} were retrieved, but the answer still needed review. Check whether the retrieved content actually supports the question.`,
    });
  }

  if (item.answer_state === "fallback") {
    guidance.push({
      id: "fallback-answer",
      tone: "warning",
      title: "Fallback answer",
      detail: "The assistant could not find grounded context and used the safe fallback response instead of answering directly.",
    });
  }

  if (item.answer_state === "low_confidence") {
    guidance.push({
      id: "low-confidence",
      tone: "warning",
      title: "Low confidence",
      detail: "The assistant produced an answer, but its confidence was below the threshold required to answer directly.",
    });
  }

  if (item.answer_state === "failed") {
    guidance.push({
      id: "failed-answer",
      tone: "danger",
      title: "Failed answer",
      detail: item.error_code ? `The request failed before a grounded answer could be generated. Error: ${item.error_code}.` : "The request failed before a grounded answer could be generated.",
    });
  }

  if (item.citation_count === 0 && (item.answer_state === "fallback" || item.answer_state === "low_confidence")) {
    guidance.push({
      id: "likely-knowledge-gap",
      tone: "danger",
      title: "Likely knowledge gap",
      detail: "No sources were retrieved and the assistant fell back or answered with low confidence. Consider adding or updating a document that covers this question.",
    });
  } else if (item.citation_count > 0 && (item.answer_state === "fallback" || item.answer_state === "low_confidence" || item.answer_state === "failed")) {
    guidance.push({
      id: "needs-document-update",
      tone: "info",
      title: "May need a document update",
      detail: "Sources were retrieved but the answer still needed review. The existing documents may be outdated, incomplete, or not a strong match for this question.",
    });
  }

  if (item.review_status === "knowledge_gap") {
    guidance.push({
      id: "confirmed-gap",
      tone: "success",
      title: "Confirmed knowledge gap",
      detail: "A reviewer already marked this as a knowledge gap. Guidance is shown for reference.",
    });
  } else if (item.review_status === "reviewed" || item.review_status === "dismissed") {
    guidance.push({
      id: "already-resolved",
      tone: "success",
      title: `Already ${item.review_status}`,
      detail: "This item has already been reviewed. Guidance is shown for reference only.",
    });
  }

  return guidance;
}

export function KnowledgeGapPanel({ item }: { item: ReviewItem }) {
  const guidance = deriveKnowledgeGuidance(item);

  return (
    <section className="reviewStoryPanel knowledgeGapPanel" aria-labelledby="knowledge-gap-title">
      <p className="sectionKicker">Knowledge improvement</p>
      <h3 id="knowledge-gap-title">Guidance from existing signals</h3>
      <div className="knowledgeGuidanceList" role="list">
        {guidance.map((entry) => {
          const Icon = TONE_ICON[entry.tone];
          return (
            <article className={`knowledgeGuidanceItem tone-${entry.tone}`} role="listitem" key={entry.id}>
              <span className="knowledgeGuidanceIcon" aria-hidden="true"><Icon size={16} /></span>
              <div>
                <strong>{entry.title}</strong>
                <p>{entry.detail}</p>
              </div>
            </article>
          );
        })}
      </div>
      <p className="reviewFilterNote"><FileWarning size={13} aria-hidden="true" style={{ marginRight: 6, verticalAlign: "middle" }} />Guidance is derived from existing answer-state, citation, and review fields only. It is not an AI-generated quality score.</p>
    </section>
  );
}
