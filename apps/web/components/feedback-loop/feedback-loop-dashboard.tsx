import Link from "next/link";

import type { EvaluationCandidate, FeedbackLoopMetrics } from "../../lib/api/feedback-loop";
import type { WidgetDetail } from "../../lib/api/widgets";

type FeedbackLoopDashboardProps = {
  assistant: WidgetDetail;
  candidates: EvaluationCandidate[];
  metrics: FeedbackLoopMetrics;
  filters: { triageStatus?: string; signalType?: string; severity?: string };
  total: number;
};

export function FeedbackLoopDashboard({ assistant, candidates, metrics, filters, total }: FeedbackLoopDashboardProps) {
  return (
    <section className="observabilityPage" aria-labelledby="feedback-loop-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">Continuous Evaluation</p>
          <h1 id="feedback-loop-title">{assistant.display_name}</h1>
          <p className="observabilitySubtitle">Production failures triaged into golden evaluation cases, with dataset versioning and regression gating.</p>
        </div>
        <nav className="observabilityTraceDetailActions" aria-label="Continuous evaluation sections">
          <Link className="smallButton" href={`/feedback-loop/versions?assistant=${assistant.id}`}>Dataset versions</Link>
          <Link className="smallButton" href={`/feedback-loop/regressions?assistant=${assistant.id}`}>Regression reports</Link>
          <Link className="smallButton" href={`/feedback-loop/runs?assistant=${assistant.id}`}>Scheduled runs</Link>
        </nav>
      </header>

      <div className="observabilityMetricGrid">
        <MetricCard label="New" value={String(metrics.candidates_by_status.new ?? 0)} detail="awaiting first triage" />
        <MetricCard label="Triaged" value={String(metrics.candidates_by_status.triaged ?? 0)} detail="classified, not yet decided" />
        <MetricCard label="Accepted" value={String(metrics.candidates_by_status.accepted ?? 0)} detail="ready to promote" />
        <MetricCard label="Resolved" value={String(metrics.candidates_by_status.resolved ?? 0)} detail="promoted and confirmed" />
        <MetricCard label="Recurrence rate" value={formatPct(metrics.recurrence_rate)} detail="candidates seen more than once" />
        <MetricCard label="Reopen rate" value={formatPct(metrics.reopen_rate)} detail="previously-resolved issues seen again" />
        <MetricCard
          label="Fixed-case confirmation"
          value={metrics.fixed_case_confirmation_rate !== null ? formatPct(metrics.fixed_case_confirmation_rate) : "N/A"}
          detail="promoted cases passing on first post-promotion run"
        />
        <MetricCard
          label="Regression escape rate"
          value={metrics.regression_escape_rate !== null ? formatPct(metrics.regression_escape_rate) : "N/A"}
          detail="promoted cases still failing after promotion"
        />
      </div>

      <CandidateFiltersForm assistantId={assistant.id} filters={filters} />

      <section aria-label="Production candidates">
        <p className="sectionKicker">Production candidates ({total})</p>
        {candidates.length === 0 ? (
          <section className="statePanel" role="status">
            <h2>No production candidates match these filters</h2>
            <p>Run the nightly signal scan, or create a candidate manually from a trace, conversation, review item, or evaluation result.</p>
          </section>
        ) : (
          <div className="observabilityTraceList" role="list">
            {candidates.map((candidate) => (
              <CandidateListRow key={candidate.id} candidate={candidate} assistantId={assistant.id} />
            ))}
          </div>
        )}
      </section>
    </section>
  );
}

function CandidateListRow({ candidate, assistantId }: { candidate: EvaluationCandidate; assistantId: string }) {
  return (
    <Link className="observabilityTraceRow" role="listitem" href={`/feedback-loop/candidates/${candidate.id}?assistant=${assistantId}`}>
      <span className={`badge answerState-${candidate.triage_status}`}>{formatEnum(candidate.triage_status)}</span>
      <span className={`badge severity-${candidate.severity}`}>{formatEnum(candidate.severity)}</span>
      <span className="observabilityTraceRowChannel">{formatEnum(candidate.signal_type)}</span>
      <span>{candidate.redacted_question ?? "(no question captured)"}</span>
      <span>{candidate.occurrence_count > 1 ? `×${candidate.occurrence_count}` : ""}</span>
      <span className="observabilityTraceRowTime">{new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(candidate.created_at))}</span>
    </Link>
  );
}

function CandidateFiltersForm({ assistantId, filters }: { assistantId: string; filters: { triageStatus?: string; signalType?: string; severity?: string } }) {
  return (
    <form className="observabilityFilters" method="get" action="/feedback-loop">
      <input type="hidden" name="assistant" value={assistantId} />
      <label>
        Triage status
        <select name="triage_status" defaultValue={filters.triageStatus ?? ""}>
          <option value="">All</option>
          <option value="new">New</option>
          <option value="triaged">Triaged</option>
          <option value="needs_information">Needs information</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
          <option value="duplicate">Duplicate</option>
          <option value="resolved">Resolved</option>
        </select>
      </label>
      <label>
        Signal type
        <select name="signal_type" defaultValue={filters.signalType ?? ""}>
          <option value="">All</option>
          <option value="fallback">Fallback</option>
          <option value="low_confidence">Low confidence</option>
          <option value="missing_citation">Missing citation</option>
          <option value="guardrail_trigger">Guardrail trigger</option>
          <option value="provider_failure">Provider failure</option>
          <option value="high_latency">High latency</option>
          <option value="support_report">Support report</option>
          <option value="manual_selection">Manual selection</option>
        </select>
      </label>
      <label>
        Severity
        <select name="severity" defaultValue={filters.severity ?? ""}>
          <option value="">All</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>
      </label>
      <button type="submit" className="actionButton">Apply filters</button>
    </form>
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

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatEnum(value: string | null | undefined): string {
  return (value ?? "unknown").replace(/_/g, " ");
}
