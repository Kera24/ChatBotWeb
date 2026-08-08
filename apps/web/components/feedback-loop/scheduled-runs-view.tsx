import Link from "next/link";

import type { EvaluationRun } from "../../lib/api/evaluation";

type ScheduledRunsViewProps = {
  runs: EvaluationRun[];
  assistantId: string;
};

export function ScheduledRunsView({ runs, assistantId }: ScheduledRunsViewProps) {
  const scheduledRuns = runs.filter((run) => Boolean(run.trigger_source));

  return (
    <section className="observabilityPage" aria-labelledby="scheduled-runs-title">
      <header className="observabilityHeader">
        <div>
          <p className="sectionKicker">Continuous Evaluation</p>
          <h1 id="scheduled-runs-title">Scheduled runs</h1>
          <p className="observabilitySubtitle">Evaluation runs triggered by a CLI (nightly, weekly, or focused) rather than the dashboard.</p>
        </div>
        <Link className="smallButton" href={`/feedback-loop?assistant=${assistantId}`}>Back to candidates</Link>
      </header>

      {scheduledRuns.length === 0 ? (
        <section className="statePanel" role="status">
          <h2>No scheduled runs recorded yet</h2>
          <p>Runs created via <code>npm run feedback:scan</code>, <code>npm run eval:focused</code>, or a cron-scheduled full run will appear here.</p>
        </section>
      ) : (
        <div className="observabilityTraceList" role="list">
          {scheduledRuns.map((run) => (
            <Link key={run.id} className="observabilityTraceRow" role="listitem" href={`/evaluation/runs/${run.id}`}>
              <span className="badge answerState-answered">{run.trigger_source}</span>
              <span className={`badge ${run.status === "completed" ? "answerState-answered" : "answerState-fallback"}`}>{run.status}</span>
              <span>{run.passed_cases}/{run.total_cases} passed</span>
              <span>{run.hard_failure_cases} hard failure(s)</span>
              <span className="observabilityTraceRowTime">{run.completed_at ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(run.completed_at)) : "in progress"}</span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
