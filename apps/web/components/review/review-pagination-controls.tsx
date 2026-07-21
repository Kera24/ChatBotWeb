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
  hasNext: boolean;
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
  hasNext,
}: ReviewPaginationControlsProps) {
  const previousOffset = Math.max(0, offset - limit);
  const nextOffset = offset + limit;
  return (
    <nav className="paginationControls" aria-label="Review queue pages">
      <Link
        aria-disabled={offset === 0}
        className={offset === 0 ? "actionButton disabledButton" : "actionButton"}
        href={buildHref(basePath, { answer_state: answerState, review_status: reviewStatus, channel, created_after: createdAfter, created_before: createdBefore, limit, offset: previousOffset })}
      >
        Previous
      </Link>
      <span>Showing {offset + 1} onward</span>
      <Link
        aria-disabled={!hasNext}
        className={!hasNext ? "actionButton disabledButton" : "actionButton"}
        href={buildHref(basePath, { answer_state: answerState, review_status: reviewStatus, channel, created_after: createdAfter, created_before: createdBefore, limit, offset: nextOffset })}
      >
        Next
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
