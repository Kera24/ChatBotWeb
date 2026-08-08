import Link from "next/link";

type CreateCandidateLinkProps = {
  sourceType: "trace" | "conversation" | "review_item" | "eval_result";
  sourceId?: string;
  assistantId?: string;
  className?: string;
  // eval_result has no FK on EvaluationCandidate (it is not a production
  // trace/conversation/message) - prefilling the question/response text
  // instead lets a reviewer turn a grader-flagged result into a candidate
  // without inventing a source relationship that doesn't exist.
  prefillQuestion?: string;
  prefillResponse?: string;
};

export function CreateCandidateLink({ sourceType, sourceId, assistantId, className, prefillQuestion, prefillResponse }: CreateCandidateLinkProps) {
  const params = new URLSearchParams({ source_type: sourceType });
  if (sourceId) params.set("source_id", sourceId);
  if (assistantId) params.set("assistant", assistantId);
  if (prefillQuestion) params.set("prefill_question", prefillQuestion);
  if (prefillResponse) params.set("prefill_response", prefillResponse);
  return (
    <Link className={className ?? "smallButton"} href={`/feedback-loop/candidates/new?${params.toString()}`}>
      Create evaluation candidate
    </Link>
  );
}
