import type { ReviewItem } from "../../lib/api/types";
import type { WidgetDetail } from "../../lib/api/widgets";

export function ReviewQualityPanel({ item, assistant, workspaceId }: { item: ReviewItem; assistant: WidgetDetail; workspaceId: string }) {
  const sourceCount = new Set(item.citations.map((citation) => citation.document_id)).size;

  return (
    <aside className="reviewQualityPanel" aria-labelledby="review-quality-title">
      <div className="reviewQualityHeader">
        <p className="sectionKicker">Review signals</p>
        <h3 id="review-quality-title">Quality &amp; metadata</h3>
      </div>

      <dl className="chatSideFacts reviewQualityFacts">
        <div><dt>Review status</dt><dd>{formatEnum(item.review_status)}</dd></div>
        <div><dt>Answer state</dt><dd>{formatEnum(item.answer_state)}</dd></div>
        <div><dt>Citations</dt><dd>{item.citation_count}</dd></div>
        <div><dt>Knowledge sources</dt><dd>{sourceCount}</dd></div>
        <div><dt>Latency</dt><dd>{item.latency_ms === null ? "No sample" : `${item.latency_ms} ms`}</dd></div>
        <div><dt>Provider</dt><dd>{item.provider_key ?? "No sample"}</dd></div>
        <div><dt>Model</dt><dd>{item.model_key ?? "No sample"}</dd></div>
        <div><dt>Assistant</dt><dd>{assistant.display_name}</dd></div>
        <div><dt>Workspace</dt><dd>{workspaceId}</dd></div>
      </dl>
    </aside>
  );
}

function formatEnum(value: string | null | undefined) {
  return (value ?? "unknown").replace(/_/g, " ");
}
