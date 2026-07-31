import Link from "next/link";

import type { AnalyticsData, AnalyticsFilters } from "../../lib/api/analytics";
import type { ConversationSummary, ReviewItem } from "../../lib/api/types";
import type { WidgetSummary } from "../../lib/api/widgets";

type AnalyticsDashboardProps = {
  data: AnalyticsData;
};

type BreakdownItem = {
  label: string;
  value: number;
};

type Insight = {
  id: string;
  tone: "warning" | "danger";
  title: string;
  detail: string;
  href: string;
};

export function AnalyticsDashboard({ data }: AnalyticsDashboardProps) {
  const metrics = calculateAnalyticsMetrics(data);
  const insights = buildInsights(data, metrics);
  const dailyConversationVolume = buildDailyVolume(data.conversations);
  const channelBreakdown = buildBreakdown(data.conversations.map((conversation) => conversation.channel));
  const statusBreakdown = buildBreakdown(data.conversations.map((conversation) => conversation.status));
  const documentBreakdown = buildBreakdown(data.documents.map((document) => document.status));
  const widgetBreakdown = buildBreakdown(data.widgets.map((widget) => widget.publication_status));

  return (
    <section className="analyticsPage" aria-labelledby="analytics-title">
      <div className="analyticsHero">
        <div>
          <p className="eyebrow">Yuranix analytics</p>
          <h2 id="analytics-title">Operational analytics from live workspace data</h2>
          <p>Track recent usage, response quality signals, knowledge failures, and widget readiness without adding product analytics or unsupported tracking.</p>
        </div>
        <div className="analyticsHeroAside" aria-label="Analytics data window">
          <strong>{data.conversations.length}</strong>
          <span>recent conversations returned</span>
        </div>
      </div>

      <AnalyticsFiltersForm filters={data.filters} />

      <section className="analyticsNotice" aria-label="Analytics data limitations">
        <strong>Data scope</strong>
        <p>Conversation and review filters are applied by the backend. Document status is filtered locally from the returned document list. Response-quality indicators use the latest {data.conversationDetails.length} conversation details from a maximum recent window of {data.recentWindowLimit} conversations.</p>
      </section>

      <section className="analyticsMetricGrid" aria-label="Usage metrics">
        {metrics.cards.map((metric) => (
          <article className="analyticsMetricCard" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <p>{metric.detail}</p>
          </article>
        ))}
      </section>

      <div className="analyticsLayout">
        <section className="analyticsPanel" aria-labelledby="usage-title">
          <div className="analyticsPanelHeader">
            <div>
              <p className="sectionKicker">Usage</p>
              <h3 id="usage-title">Conversation volume</h3>
            </div>
            <Link className="smallButton" href="/conversations">Open conversations</Link>
          </div>
          {dailyConversationVolume.length === 0 ? <AnalyticsEmpty title="No conversation volume" detail="No conversations were returned for the selected filters." /> : <BarList items={dailyConversationVolume} ariaLabel="Conversations by day" />}
        </section>

        <section className="analyticsPanel" aria-labelledby="quality-title">
          <div className="analyticsPanelHeader">
            <div>
              <p className="sectionKicker">Response quality</p>
              <h3 id="quality-title">Grounding and answer-state signals</h3>
            </div>
          </div>
          <dl className="analyticsFacts">
            <div><dt>Citation coverage</dt><dd>{metrics.citationCoverageLabel}</dd></div>
            <div><dt>Fallback rate</dt><dd>{metrics.fallbackRateLabel}</dd></div>
            <div><dt>Low-confidence responses</dt><dd>{metrics.lowConfidenceResponses}</dd></div>
            <div><dt>Average latency</dt><dd>{metrics.averageLatencyLabel}</dd></div>
            <div><dt>Total tokens</dt><dd>{metrics.totalTokensLabel}</dd></div>
          </dl>
          <p className="analyticsCaveat">Citation accuracy and answer correctness require the future evaluation framework; this page only reports fields currently exposed by operational APIs.</p>
        </section>
      </div>

      <div className="analyticsLayout">
        <section className="analyticsPanel" aria-labelledby="knowledge-title">
          <div className="analyticsPanelHeader">
            <div>
              <p className="sectionKicker">Knowledge performance</p>
              <h3 id="knowledge-title">Documents and gaps</h3>
            </div>
            <Link className="smallButton" href="/knowledge">Open knowledge base</Link>
          </div>
          <div className="analyticsSplit">
            <div>
              <h4>Document status</h4>
              {documentBreakdown.length === 0 ? <AnalyticsEmpty title="No documents" detail="No documents matched the selected document-status filter." /> : <BarList items={documentBreakdown} ariaLabel="Document status distribution" />}
            </div>
            <div>
              <h4>Recent unanswered questions</h4>
              {data.reviewItems.length === 0 ? <AnalyticsEmpty title="No open gaps" detail="No open unanswered review items matched the selected filters." /> : <ReviewTable items={data.reviewItems.slice(0, 5)} />}
            </div>
          </div>
        </section>

        <section className="analyticsPanel" aria-labelledby="widget-title">
          <div className="analyticsPanelHeader">
            <div>
              <p className="sectionKicker">Widget analytics</p>
              <h3 id="widget-title">Publication and activity readiness</h3>
            </div>
            <Link className="smallButton" href="/widgets">Manage widgets</Link>
          </div>
          {widgetBreakdown.length === 0 ? <AnalyticsEmpty title="No widgets" detail="No widgets exist in this workspace yet." /> : <BarList items={widgetBreakdown} ariaLabel="Widget publication status" />}
          <WidgetTable widgets={data.widgets.slice(0, 6)} />
        </section>
      </div>

      <div className="analyticsLayout">
        <section className="analyticsPanel" aria-labelledby="conversation-insights-title">
          <div className="analyticsPanelHeader">
            <div>
              <p className="sectionKicker">Conversation insights</p>
              <h3 id="conversation-insights-title">Source and status distribution</h3>
            </div>
          </div>
          <div className="analyticsSplit">
            <div>
              <h4>Conversation source</h4>
              {channelBreakdown.length === 0 ? <AnalyticsEmpty title="No sources" detail="No conversations were returned." /> : <BarList items={channelBreakdown} ariaLabel="Conversation source distribution" />}
            </div>
            <div>
              <h4>Conversation status</h4>
              {statusBreakdown.length === 0 ? <AnalyticsEmpty title="No statuses" detail="No conversation statuses were returned." /> : <BarList items={statusBreakdown} ariaLabel="Conversation status distribution" />}
            </div>
          </div>
        </section>

        <section className="analyticsPanel" aria-labelledby="insights-title">
          <div className="analyticsPanelHeader">
            <div>
              <p className="sectionKicker">Action required</p>
              <h3 id="insights-title">Administrator attention</h3>
            </div>
          </div>
          {insights.length === 0 ? <AnalyticsEmpty title="No action required" detail="No failed documents, inactive widgets, open gaps, or elevated fallback signals were found in the selected data." /> : <InsightList insights={insights} />}
        </section>
      </div>
    </section>
  );
}

export function AnalyticsSkeleton() {
  return (
    <section className="analyticsPage" aria-busy="true" aria-live="polite">
      <div className="analyticsHero analyticsSkeletonBlock">
        <div>
          <p className="eyebrow">Loading</p>
          <h2>Loading Yuranix analytics</h2>
          <p>Collecting tenant-scoped operational metrics.</p>
        </div>
      </div>
      <div className="analyticsMetricGrid">
        {[0, 1, 2, 3].map((item) => <div className="analyticsMetricCard analyticsSkeletonBlock" key={item} />)}
      </div>
    </section>
  );
}

export function calculateAnalyticsMetrics(data: AnalyticsData) {
  const assistantMessages = data.conversationDetails.flatMap((conversation) => conversation.messages.filter((message) => message.role === "assistant"));
  const citedResponses = assistantMessages.filter((message) => message.citations.length > 0).length;
  const fallbackResponses = assistantMessages.filter((message) => message.answer_state === "fallback" || message.answer_state === "failed").length;
  const lowConfidenceResponses = assistantMessages.filter((message) => message.answer_state === "low_confidence").length;
  const latencies = assistantMessages.map((message) => message.latency_ms).filter(isNumber);
  const tokenTotal = assistantMessages.map((message) => message.total_tokens).filter(isNumber).reduce((sum, value) => sum + value, 0);
  const activeWidgets = data.widgets.filter((widget) => widget.operational_status === "enabled" && widget.publication_status === "published").length;
  const failedDocuments = data.documents.filter((document) => document.status === "failed").length;
  const processingDocuments = data.documents.filter((document) => ["uploaded", "processing"].includes(document.status)).length;
  const citationCoverage = assistantMessages.length === 0 ? null : citedResponses / assistantMessages.length;
  const fallbackRate = assistantMessages.length === 0 ? null : fallbackResponses / assistantMessages.length;
  const averageLatency = latencies.length === 0 ? null : Math.round(latencies.reduce((sum, value) => sum + value, 0) / latencies.length);

  return {
    assistantMessageCount: assistantMessages.length,
    citedResponses,
    citationCoverage,
    citationCoverageLabel: citationCoverage === null ? "No sample" : `${Math.round(citationCoverage * 100)}%`,
    fallbackRate,
    fallbackRateLabel: fallbackRate === null ? "No sample" : `${Math.round(fallbackRate * 100)}%`,
    lowConfidenceResponses,
    averageLatencyLabel: averageLatency === null ? "No sample" : `${averageLatency} ms`,
    totalTokensLabel: tokenTotal === 0 ? "No sample" : String(tokenTotal),
    cards: [
      { label: "Recent conversations", value: String(data.conversations.length), detail: `Returned from a maximum recent window of ${data.recentWindowLimit}.` },
      { label: "Messages", value: String(data.conversations.reduce((sum, conversation) => sum + conversation.message_count, 0)), detail: "Message counts from conversation summaries." },
      { label: "Open knowledge gaps", value: String(data.reviewTotal), detail: "Open unanswered review items in the selected period." },
      { label: "Active widgets", value: `${activeWidgets}/${data.widgets.length}`, detail: "Published and operational widgets." },
      { label: "Failed documents", value: String(failedDocuments), detail: "Documents in failed lifecycle state." },
      { label: "Processing documents", value: String(processingDocuments), detail: "Documents uploaded or processing." },
    ],
  };
}

function AnalyticsFiltersForm({ filters }: { filters: AnalyticsFilters }) {
  return (
    <form className="analyticsFilters" aria-label="Analytics filters">
      <label>
        Started after
        <input type="date" name="started_after" defaultValue={toDateInput(filters.started_after)} />
      </label>
      <label>
        Started before
        <input type="date" name="started_before" defaultValue={toDateInput(filters.started_before)} />
      </label>
      <label>
        Source
        <select name="conversation_channel" defaultValue={filters.conversation_channel || ""}>
          <option value="">All sources</option>
          <option value="dashboard_test">Dashboard test</option>
          <option value="widget">Widget</option>
          <option value="api">API</option>
          <option value="future_integration">Future integration</option>
        </select>
      </label>
      <label>
        Conversation status
        <select name="conversation_status" defaultValue={filters.conversation_status || ""}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="abandoned">Abandoned</option>
          <option value="archived">Archived</option>
        </select>
      </label>
      <label>
        Document status
        <select name="document_status" defaultValue={filters.document_status || ""}>
          <option value="">All documents</option>
          <option value="uploaded">Uploaded</option>
          <option value="processing">Processing</option>
          <option value="ready">Ready</option>
          <option value="failed">Failed</option>
          <option value="archived">Archived</option>
        </select>
      </label>
      <div className="analyticsFilterActions">
        <button className="actionButton" type="submit">Apply filters</button>
        <Link className="smallButton" href="/analytics">Reset</Link>
      </div>
    </form>
  );
}

function BarList({ items, ariaLabel }: { items: BreakdownItem[]; ariaLabel: string }) {
  const max = Math.max(...items.map((item) => item.value), 1);
  return (
    <div className="analyticsBarList" role="list" aria-label={ariaLabel}>
      {items.map((item) => (
        <div className="analyticsBarItem" role="listitem" key={item.label}>
          <div className="analyticsBarLabel"><span>{formatLabel(item.label)}</span><strong>{item.value}</strong></div>
          <div className="analyticsBarTrack" aria-hidden="true"><span style={{ width: `${Math.max(8, (item.value / max) * 100)}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

function ReviewTable({ items }: { items: ReviewItem[] }) {
  return (
    <div className="analyticsTableWrap">
      <table className="analyticsTable">
        <thead><tr><th>Question</th><th>State</th><th>Created</th></tr></thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.assistant_message_id}>
              <td><Link href={`/review/unanswered/${item.assistant_message_id}`}>{item.user_question || "Question unavailable"}</Link></td>
              <td>{formatLabel(item.answer_state)}</td>
              <td>{formatDate(item.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WidgetTable({ widgets }: { widgets: WidgetSummary[] }) {
  if (widgets.length === 0) return null;
  return (
    <div className="analyticsTableWrap compactTable">
      <table className="analyticsTable">
        <thead><tr><th>Widget</th><th>Publication</th><th>Operational</th></tr></thead>
        <tbody>
          {widgets.map((widget) => (
            <tr key={widget.id}>
              <td><Link href={`/widgets/${widget.id}`}>{widget.display_name}</Link></td>
              <td>{formatLabel(widget.publication_status)}</td>
              <td>{formatLabel(widget.operational_status)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function InsightList({ insights }: { insights: Insight[] }) {
  return (
    <div className="analyticsInsightList" role="list">
      {insights.map((insight) => (
        <article className={`analyticsInsight analytics-insight-${insight.tone}`} role="listitem" key={insight.id}>
          <div>
            <h4>{insight.title}</h4>
            <p>{insight.detail}</p>
          </div>
          <Link className="smallButton" href={insight.href}>Open</Link>
        </article>
      ))}
    </div>
  );
}

function AnalyticsEmpty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="analyticsEmptyState">
      <h4>{title}</h4>
      <p>{detail}</p>
    </div>
  );
}

function buildInsights(data: AnalyticsData, metrics: ReturnType<typeof calculateAnalyticsMetrics>): Insight[] {
  const failedDocuments = data.documents.filter((document) => document.status === "failed").length;
  const stuckDocuments = data.documents.filter((document) => ["uploaded", "processing"].includes(document.status) && minutesSince(document.updated_at) > 30).length;
  const inactiveWidgets = data.widgets.filter((widget) => widget.operational_status !== "enabled" || widget.publication_status !== "published").length;
  const insights: Insight[] = [];

  if (data.reviewTotal > 0) insights.push({ id: "review-backlog", tone: "warning", title: "Knowledge review backlog", detail: `${data.reviewTotal} open unanswered review item needs attention.`, href: "/review/unanswered" });
  if (failedDocuments > 0) insights.push({ id: "failed-documents", tone: "danger", title: "Document processing failures", detail: `${failedDocuments} document failed ingestion or processing.`, href: "/knowledge" });
  if (stuckDocuments > 0) insights.push({ id: "stuck-documents", tone: "warning", title: "Processing may be stuck", detail: `${stuckDocuments} document has not changed for more than 30 minutes.`, href: "/knowledge" });
  if (inactiveWidgets > 0) insights.push({ id: "inactive-widgets", tone: "warning", title: "Inactive widgets", detail: `${inactiveWidgets} widget is not both published and enabled.`, href: "/widgets" });
  if (metrics.fallbackRate !== null && metrics.fallbackRate >= 0.25) insights.push({ id: "fallback-rate", tone: "warning", title: "Elevated fallback rate", detail: `${metrics.fallbackRateLabel} of sampled assistant responses were fallback or failed.`, href: "/review/unanswered" });
  if (metrics.citationCoverage !== null && metrics.citationCoverage < 0.5) insights.push({ id: "low-citations", tone: "warning", title: "Low citation coverage", detail: `${metrics.citationCoverageLabel} of sampled assistant responses included citations.`, href: "/conversations" });

  return insights;
}

function buildDailyVolume(conversations: ConversationSummary[]): BreakdownItem[] {
  const counts = new Map<string, number>();
  for (const conversation of conversations) {
    const key = new Date(conversation.started_at).toISOString().slice(0, 10);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([label, value]) => ({ label, value }));
}

function buildBreakdown(values: string[]): BreakdownItem[] {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value || "unknown", (counts.get(value || "unknown") ?? 0) + 1);
  return [...counts.entries()].sort((left, right) => right[1] - left[1]).map(([label, value]) => ({ label, value }));
}

function isNumber(value: number | null): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function toDateInput(value: string | undefined) {
  if (!value) return "";
  return value.slice(0, 10);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}

function formatLabel(value: string) {
  return value.replace(/_/g, " ");
}

function minutesSince(value: string) {
  return (Date.now() - new Date(value).getTime()) / 60_000;
}


