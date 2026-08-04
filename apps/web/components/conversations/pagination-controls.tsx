import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

type PaginationControlsProps = {
  basePath: string;
  status?: string;
  channel?: string;
  limit: number;
  offset: number;
  hasNext: boolean;
  assistantId: string;
};

export function PaginationControls({ basePath, status, channel, limit, offset, hasNext, assistantId }: PaginationControlsProps) {
  const previousOffset = Math.max(0, offset - limit);
  const nextOffset = offset + limit;
  const rangeEnd = offset + limit;

  return (
    <nav className="paginationControls premiumPaginationControls" aria-label="Conversation pages">
      <Link
        aria-disabled={offset === 0}
        className={offset === 0 ? "actionButton disabledButton" : "actionButton"}
        href={buildHref(basePath, { assistant: assistantId, status, channel, limit, offset: previousOffset })}
        tabIndex={offset === 0 ? -1 : undefined}
      >
        <ChevronLeft size={16} aria-hidden="true" />
        Previous
      </Link>
      <span>Showing {offset + 1}{"–"}{rangeEnd}</span>
      <Link
        aria-disabled={!hasNext}
        className={!hasNext ? "actionButton disabledButton" : "actionButton"}
        href={buildHref(basePath, { assistant: assistantId, status, channel, limit, offset: nextOffset })}
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
