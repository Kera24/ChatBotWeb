import Link from "next/link";

import type { EvaluationRegressionReport } from "../../lib/api/feedback-loop";

type RegressionReportsViewProps = {
  reports: EvaluationRegressionReport[];
  assistantId: string;
};

export function RegressionReportsView({ reports, assistantId }: RegressionReportsViewProps) {
  return (
    <section className="observabilityPage" aria-labelledby="regression-reports-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">Continuous Evaluation</p>
          <h1 id="regression-reports-title">Regression reports</h1>
          <p className="observabilitySubtitle">Every scheduled or manual comparison against a baseline run, with new/fixed/newly-failing case breakdowns.</p>
        </div>
        <Link className="smallButton" href={`/feedback-loop?assistant=${assistantId}`}>Back to candidates</Link>
      </header>

      {reports.length === 0 ? (
        <section className="statePanel" role="status">
          <h2>No regression reports yet</h2>
          <p>Run <code>npm run eval:regression-report</code> against two evaluation runs to produce one.</p>
        </section>
      ) : (
        <div className="observabilityTraceList" role="list">
          {reports.map((report) => {
            const newCases = Array.isArray(report.report_json.new_cases) ? report.report_json.new_cases.length : 0;
            const fixedCases = Array.isArray(report.report_json.fixed_cases) ? report.report_json.fixed_cases.length : 0;
            const newlyFailingCases = Array.isArray(report.report_json.newly_failing_cases) ? report.report_json.newly_failing_cases.length : 0;
            return (
              <div key={report.id} className="observabilityTraceRow" role="listitem">
                <span className={`badge ${report.verdict_passed ? "answerState-answered" : "answerState-fallback"}`}>{report.verdict_passed ? "Passed" : "Failed"}</span>
                <span>run {report.run_id.slice(0, 8)} vs. baseline {report.baseline_run_id ? report.baseline_run_id.slice(0, 8) : "none"}</span>
                <span>{newCases} new · {fixedCases} fixed · {newlyFailingCases} newly failing</span>
                <span>{report.created_by ?? "unknown"}</span>
                <span className="observabilityTraceRowTime">{new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(report.created_at))}</span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
