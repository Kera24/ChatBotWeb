import Link from "next/link";

import type { AIAnomalySignal, AIObservabilityMetrics, AITraceSummary } from "../../lib/api/observability";
import type { WidgetDetail } from "../../lib/api/widgets";

type ObservabilityDashboardProps = {
  assistant: WidgetDetail;
  metrics: AIObservabilityMetrics;
  traces: AITraceSummary[];
  anomalies: AIAnomalySignal[];
  filters: { status?: string; answerState?: string; providerKey?: string; modelKey?: string };
};

export function ObservabilityDashboard({ assistant, metrics, traces, anomalies, filters }: ObservabilityDashboardProps) {
  const triggeredAnomalies = anomalies.filter((signal) => signal.triggered);

  return (
    <section className="observabilityPage" aria-labelledby="observability-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">AI Observability</p>
          <h1 id="observability-title">{assistant.display_name}</h1>
          <p className="observabilitySubtitle">Explain every request: input policy → retrieval → guardrails → provider call → response.</p>
        </div>
        <Link className="actionButton" href={`/observability?assistant=${assistant.id}`}>Refresh</Link>
      </header>

      <div className="observabilityMetricGrid">
        <MetricCard label="Requests" value={metrics.request_volume.toLocaleString()} detail="in the current filtered window" />
        <MetricCard label="p50 / p95 latency" value={`${formatMs(metrics.p50_latency_ms)} / ${formatMs(metrics.p95_latency_ms)}`} detail="end-to-end request latency" />
        <MetricCard label="Tokens" value={metrics.total_tokens.toLocaleString()} detail="input + output, all model calls" />
        <MetricCard
          label="Estimated cost"
          value={metrics.total_estimated_cost !== null ? `$${Number(metrics.total_estimated_cost).toFixed(4)}` : "Unknown"}
          detail={metrics.unknown_cost_request_count > 0 ? `${metrics.unknown_cost_request_count} request(s) have no configured pricing` : "all requests priced"}
        />
        <MetricCard label="Fallback rate" value={formatPct(metrics.fallback_rate)} detail={`${metrics.fallback_count} of ${metrics.request_volume} requests`} />
        <MetricCard label="Blocked rate" value={formatPct(metrics.blocked_rate)} detail="guardrail-blocked requests" />
        <MetricCard label="Provider failure rate" value={formatPct(metrics.provider_failure_rate)} detail={`${metrics.failed_count} failed request(s)`} />
        <MetricCard
          label="Citation coverage"
          value={metrics.citation_coverage !== null ? formatPct(metrics.citation_coverage) : "N/A"}
          detail="answered responses with a selected citation"
        />
        <MetricCard label="Evidence-insufficient rate" value={formatPct(metrics.evidence_insufficient_rate)} detail="requests where retrieved evidence did not support the specific fact asked" />
      </div>

      <ObservabilityFiltersForm assistantId={assistant.id} filters={filters} />

      {triggeredAnomalies.length > 0 ? (
        <section className="observabilityAnomalyPanel urgentState" aria-label="Anomaly signals">
          <p className="sectionKicker">Trend signals (24h vs. trailing 7-day baseline)</p>
          <ul className="observabilityAnomalyList">
            {triggeredAnomalies.map((signal) => (
              <li key={signal.metric}>
                <strong>{formatMetricName(signal.metric)}</strong>{" "}
                {signal.direction === "up" ? "increased" : signal.direction === "down" ? "decreased" : "changed"} by{" "}
                {signal.relative_change_pct !== null ? `${Math.abs(signal.relative_change_pct).toFixed(0)}%` : "an unmeasured amount"} vs. baseline.
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-label="Recent traces">
        <p className="sectionKicker">Recent traces</p>
        {traces.length === 0 ? (
          <section className="statePanel" role="status">
            <h2>No AI traces recorded yet</h2>
            <p>Once this assistant answers a question (dashboard test or public widget), traces will appear here.</p>
          </section>
        ) : (
          <div className="observabilityTraceList" role="list">
            {traces.map((trace) => (
              <TraceListRow key={trace.trace_id} trace={trace} assistantId={assistant.id} />
            ))}
          </div>
        )}
      </section>
    </section>
  );
}

function TraceListRow({ trace, assistantId }: { trace: AITraceSummary; assistantId: string }) {
  return (
    <Link className="observabilityTraceRow" role="listitem" href={`/observability/traces/${trace.trace_id}?assistant=${assistantId}`}>
      <span className={`badge answerState-${trace.answer_state ?? "unknown"}`}>{formatEnum(trace.answer_state)}</span>
      <span className="observabilityTraceRowChannel">{formatEnum(trace.channel)}</span>
      <span className="observabilityTraceRowModel">{trace.model_key ?? "-"}</span>
      <span>{formatMs(trace.total_latency_ms)}</span>
      <span>{trace.total_tokens?.toLocaleString() ?? "-"} tok</span>
      <span>{trace.estimated_cost !== null ? `$${Number(trace.estimated_cost).toFixed(4)}` : "unknown cost"}</span>
      <span className="observabilityTraceRowTime">{new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(trace.created_at))}</span>
    </Link>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="card observabilityMetricCard">
      <p className="observabilityMetricLabel">{label}</p>
      <strong className="metricValue observabilityMetricValue">{value}</strong>
      <p className="observabilityMetricDetail">{detail}</p>
    </div>
  );
}

function ObservabilityFiltersForm({ assistantId, filters }: { assistantId: string; filters: { status?: string; answerState?: string; providerKey?: string; modelKey?: string } }) {
  return (
    <form className="observabilityFilters" method="get" action="/observability">
      <input type="hidden" name="assistant" value={assistantId} />
      <label>
        Answer state
        <select name="answer_state" defaultValue={filters.answerState ?? ""}>
          <option value="">All</option>
          <option value="answered">Answered</option>
          <option value="fallback">Fallback</option>
          <option value="failed">Failed</option>
        </select>
      </label>
      <label>
        Status
        <select name="status" defaultValue={filters.status ?? ""}>
          <option value="">All</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="in_progress">In progress</option>
        </select>
      </label>
      <label>
        Provider
        <input type="text" name="provider_key" defaultValue={filters.providerKey ?? ""} placeholder="e.g. mock" />
      </label>
      <label>
        Model
        <input type="text" name="model_key" defaultValue={filters.modelKey ?? ""} placeholder="e.g. mock-grounded-answer" />
      </label>
      <button type="submit" className="actionButton">Apply filters</button>
    </form>
  );
}

function formatMs(value: number | null): string {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value).toLocaleString()}ms`;
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatEnum(value: string | null | undefined): string {
  return (value ?? "unknown").replace(/_/g, " ");
}

function formatMetricName(metric: string): string {
  return metric.replace(/_/g, " ");
}
