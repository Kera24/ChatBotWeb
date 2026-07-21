type ConversationFiltersProps = {
  status?: string;
  channel?: string;
  limit: number;
};

export function ConversationFilters({ status, channel, limit }: ConversationFiltersProps) {
  return (
    <form className="conversationControls" aria-label="Conversation filters">
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
      <button className="actionButton" type="submit" aria-label="Apply conversation filters">Apply</button>
    </form>
  );
}
