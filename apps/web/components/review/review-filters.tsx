import Link from "next/link";

type ReviewFiltersProps = {
  answerState?: string;
  reviewStatus?: string;
  channel?: string;
  createdAfter?: string;
  createdBefore?: string;
  limit: number;
  assistantId: string;
};

const ANSWER_STATE_LABELS: Record<string, string> = {
  fallback: "Fallback",
  failed: "Failed",
  low_confidence: "Low confidence",
};

const REVIEW_STATUS_LABELS: Record<string, string> = {
  open: "Open",
  reviewed: "Reviewed",
  dismissed: "Dismissed",
  knowledge_gap: "Knowledge gap",
};

const CHANNEL_LABELS: Record<string, string> = {
  dashboard_test: "Dashboard test",
  widget: "Widget",
  api: "API",
  future_integration: "Future integration",
};

export function ReviewFilters({ answerState, reviewStatus, channel, createdAfter, createdBefore, limit, assistantId }: ReviewFiltersProps) {
  const activeFilters = buildActiveFilters({ answerState, reviewStatus, channel, createdAfter, createdBefore }, assistantId);

  return (
    <div className="reviewFilterBar" aria-label="Review queue filters and active filter summary">
      <form className="conversationControls reviewControls premiumReviewControls" aria-label="Review queue filters">
        <input type="hidden" name="assistant" value={assistantId} />
        <label>
          <span>Answer state</span>
          <select name="answer_state" defaultValue={answerState ?? ""}>
            <option value="">All flagged states</option>
            <option value="fallback">Fallback</option>
            <option value="failed">Failed</option>
            <option value="low_confidence">Low confidence</option>
          </select>
        </label>
        <label>
          <span>Review status</span>
          <select name="review_status" defaultValue={reviewStatus ?? ""}>
            <option value="">All review statuses</option>
            <option value="open">Open</option>
            <option value="reviewed">Reviewed</option>
            <option value="dismissed">Dismissed</option>
            <option value="knowledge_gap">Knowledge gap</option>
          </select>
        </label>
        <label>
          <span>Channel</span>
          <select name="channel" defaultValue={channel ?? ""}>
            <option value="">All channels</option>
            <option value="dashboard_test">Dashboard test</option>
            <option value="widget">Widget</option>
            <option value="api">API</option>
            <option value="future_integration">Future integration</option>
          </select>
        </label>
        <label>
          <span>After</span>
          <input name="created_after" type="date" defaultValue={createdAfter ?? ""} />
        </label>
        <label>
          <span>Before</span>
          <input name="created_before" type="date" defaultValue={createdBefore ?? ""} />
        </label>
        <label>
          <span>Page size</span>
          <select name="limit" defaultValue={String(limit)}>
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
        </label>
        <div className="reviewFilterFormActions">
          <button className="actionButton" type="submit" aria-label="Apply review filters">Apply filters</button>
          <Link className="smallButton" href={`/review/unanswered?assistant=${assistantId}`} aria-label="Clear all review filters">Clear all</Link>
        </div>
      </form>

      {activeFilters.length > 0 ? (
        <ul className="reviewActiveFilters" aria-label="Active review filters">
          {activeFilters.map((filter) => (
            <li key={filter.key}>
              <span>{filter.label}</span>
              <Link href={filter.clearHref} aria-label={`Remove filter: ${filter.label}`}>&times;</Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="reviewFilterNote">No filters applied. Showing the most recent flagged items for this assistant.</p>
      )}
    </div>
  );
}

function buildActiveFilters(
  filters: { answerState?: string; reviewStatus?: string; channel?: string; createdAfter?: string; createdBefore?: string },
  assistantId: string,
) {
  const active: Array<{ key: string; label: string; clearHref: string }> = [];
  const base: Record<string, string | undefined> = {
    assistant: assistantId,
    answer_state: filters.answerState,
    review_status: filters.reviewStatus,
    channel: filters.channel,
    created_after: filters.createdAfter,
    created_before: filters.createdBefore,
  };

  if (filters.answerState) active.push({ key: "answer_state", label: `Answer state: ${ANSWER_STATE_LABELS[filters.answerState] ?? filters.answerState}`, clearHref: buildHref({ ...base, answer_state: undefined }) });
  if (filters.reviewStatus) active.push({ key: "review_status", label: `Review status: ${REVIEW_STATUS_LABELS[filters.reviewStatus] ?? filters.reviewStatus}`, clearHref: buildHref({ ...base, review_status: undefined }) });
  if (filters.channel) active.push({ key: "channel", label: `Channel: ${CHANNEL_LABELS[filters.channel] ?? filters.channel}`, clearHref: buildHref({ ...base, channel: undefined }) });
  if (filters.createdAfter) active.push({ key: "created_after", label: `Created after ${filters.createdAfter}`, clearHref: buildHref({ ...base, created_after: undefined }) });
  if (filters.createdBefore) active.push({ key: "created_before", label: `Created before ${filters.createdBefore}`, clearHref: buildHref({ ...base, created_before: undefined }) });

  return active;
}

function buildHref(params: Record<string, string | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, value);
  }
  const query = search.toString();
  return query ? `/review/unanswered?${query}` : "/review/unanswered";
}
