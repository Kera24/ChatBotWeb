import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

type ReviewPaginationControlsProps = {
  basePath: string;
  answerState?: string;
  reviewStatus?: string;
  channel?: string;
  createdAfter?: string;
  createdBefore?: string;
  limit: number;
  offset: number;
  total: number;
  hasNext: boolean;
  assistantId: string;
};

export function ReviewPaginationControls({
  basePath,
  answerState,
  reviewStatus,
  channel,
  createdAfter,
  createdBefore,
  limit,
  offset,
  total,
  hasNext,
  assistantId,
}: ReviewPaginationControlsProps) {
  const previousOffset = Math.max(0, offset - limit);
  const nextOffset = offset + limit;
  const rangeEnd = Math.min(total, offset + limit);

  return (
    <nav className="paginationControls premiumPaginationControls" aria-label="Review queue pages">
      <Link
        aria-disabled={offset === 0}
        className={offset === 0 ? "actionButton disabledButton" : "actionButton"}
        href={buildHref(basePath, { assistant: assistantId, answer_state: answerState, review_status: reviewStatus, channel, created_after: createdAfter, created_before: createdBefore, limit, offset: previousOffset })}
        tabIndex={offset === 0 ? -1 : undefined}
      >
        <ChevronLeft size={16} aria-hidden="true" />
        Previous
      </Link>
      <span>{total === 0 ? "No results" : `Showing ${offset + 1}–${rangeEnd} of ${total}`}</span>
      <Link
        aria-disabled={!hasNext}
        className={!hasNext ? "actionButton disabledButton" : "actionButton"}
        href={buildHref(basePath, { assistant: assistantId, answer_state: answerState, review_status: reviewStatus, channel, created_after: createdAfter, created_before: createdBefore, limit, offset: nextOffset })}
        tabIndex={!hasNext ? -1 : undefined}
      >
        Next
        <ChevronRight size={16} aria-hidden="true" />
      </Link>
    </nav>
  );
}

function buildHref(basePath: string, params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `${basePath}?${query}` : basePath;
}
