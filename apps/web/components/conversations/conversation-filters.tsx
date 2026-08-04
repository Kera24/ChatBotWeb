import Link from "next/link";

type ConversationFiltersProps = {
  status?: string;
  channel?: string;
  limit: number;
  assistantId: string;
  startedAfter?: string;
  startedBefore?: string;
};

const STATUS_LABELS: Record<string, string> = {
  active: "Active",
  completed: "Completed",
  abandoned: "Abandoned",
  archived: "Archived",
};

const CHANNEL_LABELS: Record<string, string> = {
  dashboard_test: "Dashboard test",
  widget: "Widget",
  api: "API",
  future_integration: "Future integration",
};

export function ConversationFilters({ status, channel, limit, assistantId, startedAfter, startedBefore }: ConversationFiltersProps) {
  const activeFilters = buildActiveFilters({ status, channel, startedAfter, startedBefore }, assistantId);

  return (
    <div className="conversationFilterBar" aria-label="Conversation filters and active filter summary">
      <form className="conversationControls premiumConversationControls" aria-label="Conversation filters">
        <input type="hidden" name="assistant" value={assistantId} />
        <label>
          <span>Started after</span>
          <input type="date" name="started_after" defaultValue={startedAfter ?? ""} />
        </label>
        <label>
          <span>Started before</span>
          <input type="date" name="started_before" defaultValue={startedBefore ?? ""} />
        </label>
        <label>
          <span>Status</span>
          <select name="status" defaultValue={status ?? ""}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="completed">Completed</option>
            <option value="abandoned">Abandoned</option>
            <option value="archived">Archived</option>
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
          <span>Page size</span>
          <select name="limit" defaultValue={String(limit)}>
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
        </label>
        <div className="conversationFilterFormActions">
          <button className="actionButton" type="submit" aria-label="Apply conversation filters">Apply filters</button>
          <Link className="smallButton" href={`/conversations?assistant=${assistantId}`} aria-label="Clear all conversation filters">Clear all</Link>
        </div>
      </form>

      {activeFilters.length > 0 ? (
        <ul className="conversationActiveFilters" aria-label="Active conversation filters">
          {activeFilters.map((filter) => (
            <li key={filter.key}>
              <span>{filter.label}</span>
              <Link href={filter.clearHref} aria-label={`Remove filter: ${filter.label}`}>&times;</Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="conversationFilterNote">No filters applied. Showing the most recent conversations for this assistant.</p>
      )}

      <p className="conversationFilterNote">Search is not available yet; filters apply only to fields already returned by the conversation list API.</p>
    </div>
  );
}

function buildActiveFilters(
  filters: { status?: string; channel?: string; startedAfter?: string; startedBefore?: string },
  assistantId: string,
) {
  const active: Array<{ key: string; label: string; clearHref: string }> = [];
  const base: Record<string, string | undefined> = {
    assistant: assistantId,
    status: filters.status,
    channel: filters.channel,
    started_after: filters.startedAfter,
    started_before: filters.startedBefore,
  };

  if (filters.status) active.push({ key: "status", label: `Status: ${STATUS_LABELS[filters.status] ?? filters.status}`, clearHref: buildHref({ ...base, status: undefined }) });
  if (filters.channel) active.push({ key: "channel", label: `Channel: ${CHANNEL_LABELS[filters.channel] ?? filters.channel}`, clearHref: buildHref({ ...base, channel: undefined }) });
  if (filters.startedAfter) active.push({ key: "started_after", label: `Started after ${filters.startedAfter}`, clearHref: buildHref({ ...base, started_after: undefined }) });
  if (filters.startedBefore) active.push({ key: "started_before", label: `Started before ${filters.startedBefore}`, clearHref: buildHref({ ...base, started_before: undefined }) });

  return active;
}

function buildHref(params: Record<string, string | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, value);
  }
  const query = search.toString();
  return query ? `/conversations?${query}` : "/conversations";
}
