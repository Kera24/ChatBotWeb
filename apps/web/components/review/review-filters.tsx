type ReviewFiltersProps = {
  answerState?: string;
  reviewStatus?: string;
  channel?: string;
  createdAfter?: string;
  createdBefore?: string;
  limit: number;
};

export function ReviewFilters({ answerState, reviewStatus, channel, createdAfter, createdBefore, limit }: ReviewFiltersProps) {
  return (
    <form className="conversationControls reviewControls" aria-label="Review queue filters">
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
      <button className="actionButton" type="submit" aria-label="Apply review filters">Apply</button>
    </form>
  );
}
