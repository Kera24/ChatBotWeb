import Link from "next/link";

type PaginationControlsProps = {
  basePath: string;
  status?: string;
  channel?: string;
  limit: number;
  offset: number;
  hasNext: boolean;
};

export function PaginationControls({ basePath, status, channel, limit, offset, hasNext }: PaginationControlsProps) {
  const previousOffset = Math.max(0, offset - limit);
  const nextOffset = offset + limit;

  return (
    <nav className="paginationControls" aria-label="Conversation pages">
      <Link
        aria-disabled={offset === 0}
        className={offset === 0 ? "actionButton disabledButton" : "actionButton"}
        href={buildHref(basePath, { status, channel, limit, offset: previousOffset })}
      >
        Previous
      </Link>
      <span>Showing {offset + 1} onward</span>
      <Link
        aria-disabled={!hasNext}
        className={!hasNext ? "actionButton disabledButton" : "actionButton"}
        href={buildHref(basePath, { status, channel, limit, offset: nextOffset })}
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
