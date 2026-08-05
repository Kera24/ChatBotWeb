import Link from "next/link";

import { AccessDeniedState, ErrorState } from "../../../../components/conversations/state-panels";
import { EvaluationStatusBadge } from "../../../../components/evaluation/badges";
import { formatCategory, formatDateTime, formatMs, formatPercent, toneForCase, toneForGate, toneForRunStatus } from "../../../../components/evaluation/format";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../../lib/api/errors";
import { compareEvaluationRuns, getEvaluationRun, listEvaluationRunResults, listEvaluationRuns } from "../../../../lib/api/evaluation";
import type { DevelopmentDashboardSession } from "../../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../../lib/auth/session";

export const dynamic = "force-dynamic";

type EvaluationRunPageProps = {
  params: Promise<{ runId: string }>;
  searchParams: Promise<{ compareTo?: string }>;
};

export default async function EvaluationRunPage({ params, searchParams }: EvaluationRunPageProps) {
  const { runId } = await params;
  const { compareTo } = await searchParams;
  const session = await requireDashboardSession();

  const result = await loadRunDetail(session, runId);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/evaluation" />;
  }

  const { run, summary, gate, results, otherRuns } = result.data;
  const comparison = compareTo ? await loadComparison(session, compareTo, runId) : null;

  return (
    <>
      <Link className="backLink" href="/evaluation">Back to evaluation</Link>
      <section className="evaluationPage" aria-labelledby="evaluation-run-title">
        <div className="widgetHero">
          <div>
            <p className="eyebrow">Evaluation run · {run.mode}</p>
            <h2 id="evaluation-run-title">Run {run.id.slice(0, 8)}</h2>
            <p>
              Dataset {run.dataset_id} @ version {run.dataset_version} · Model {run.model_key || "—"} · Provider {run.provider_key || "—"}
            </p>
          </div>
          <div className="widgetHeroAside">
            <strong>{formatPercent(summary.pass_rate)}</strong>
            <span>pass rate</span>
          </div>
        </div>

        <div className="widgetPanel">
          <h2>Gate verdict</h2>
          <p><EvaluationStatusBadge label={gate.passed ? "gate passed" : "gate failed"} tone={toneForGate(gate.passed)} /></p>
          {gate.reasons.length > 0 ? (
            <ul>
              {gate.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : (
            <p>No release-blocking issues found against the configured policy.</p>
          )}
        </div>

        <div className="widgetPanel">
          <h2>Summary</h2>
          <dl className="widgetFacts">
            <div><dt>Status</dt><dd><EvaluationStatusBadge label={run.status} tone={toneForRunStatus(run.status)} /></dd></div>
            <div><dt>Cases</dt><dd>{summary.total_cases}</dd></div>
            <div><dt>Passed / failed</dt><dd>{summary.passed_cases} / {summary.failed_cases}</dd></div>
            <div><dt>Hard failures</dt><dd>{summary.hard_failure_cases}</dd></div>
            <div><dt>Retrieval hit rate</dt><dd>{formatPercent(summary.retrieval_hit_rate)}</dd></div>
            <div><dt>Citation coverage</dt><dd>{formatPercent(summary.citation_coverage)}</dd></div>
            <div><dt>Fallback rate (answerable)</dt><dd>{formatPercent(summary.fallback_rate_on_answerable)}</dd></div>
            <div><dt>Correct fallback (unanswerable)</dt><dd>{formatPercent(summary.correct_fallback_rate_on_unanswerable)}</dd></div>
            <div><dt>Latency p50 / p95</dt><dd>{formatMs(summary.latency_p50_ms)} / {formatMs(summary.latency_p95_ms)}</dd></div>
            <div><dt>Total tokens</dt><dd>{summary.total_tokens}</dd></div>
            <div><dt>Started</dt><dd>{formatDateTime(run.started_at)}</dd></div>
            <div><dt>Completed</dt><dd>{formatDateTime(run.completed_at)}</dd></div>
          </dl>
        </div>

        <div className="widgetPanel">
          <h2>Category breakdown</h2>
          <table>
            <thead>
              <tr>
                <th scope="col">Category</th>
                <th scope="col">Total</th>
                <th scope="col">Passed</th>
                <th scope="col">Failed</th>
                <th scope="col">Hard failures</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.category_breakdown).map(([category, counts]) => (
                <tr key={category}>
                  <td>{formatCategory(category)}</td>
                  <td>{counts.total}</td>
                  <td>{counts.passed}</td>
                  <td>{counts.failed}</td>
                  <td>{counts.hard_failure}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {otherRuns.length > 0 ? (
          <div className="widgetPanel">
            <h2>Compare against a baseline run</h2>
            <form method="get">
              <label htmlFor="compareTo">Baseline run</label>
              <select id="compareTo" name="compareTo" defaultValue={compareTo || ""}>
                <option value="">Select a previous run…</option>
                {otherRuns.map((otherRun) => (
                  <option key={otherRun.id} value={otherRun.id}>
                    {otherRun.id.slice(0, 8)} · {formatDateTime(otherRun.created_at)}
                  </option>
                ))}
              </select>
              <button className="actionButton" type="submit">Compare</button>
            </form>
            {comparison ? (
              <dl className="widgetFacts">
                <div><dt>Baseline pass rate</dt><dd>{formatPercent(comparison.comparison.baseline_pass_rate)}</dd></div>
                <div><dt>Candidate pass rate</dt><dd>{formatPercent(comparison.comparison.candidate_pass_rate)}</dd></div>
                <div><dt>Pass rate delta</dt><dd>{formatPercent(comparison.comparison.pass_rate_delta)}</dd></div>
                <div><dt>Hard failures (baseline / candidate)</dt><dd>{comparison.comparison.baseline_hard_failure_cases} / {comparison.comparison.candidate_hard_failure_cases}</dd></div>
                <div>
                  <dt>Regressed</dt>
                  <dd><EvaluationStatusBadge label={comparison.comparison.regressed ? "regressed" : "no regression"} tone={toneForGate(!comparison.comparison.regressed)} /></dd>
                </div>
              </dl>
            ) : null}
          </div>
        ) : null}

        <section aria-labelledby="evaluation-run-results-title">
          <p className="sectionKicker" id="evaluation-run-results-title">Case results</p>
          {results.length === 0 ? (
            <div className="statePanel">
              <p className="sectionKicker">No results</p>
              <h2>This run has no recorded results</h2>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Latency</th>
                  <th scope="col">Failure reasons</th>
                </tr>
              </thead>
              <tbody>
                {results.map((caseResult) => (
                  <tr key={caseResult.id}>
                    <td><Link href={`/evaluation/runs/${run.id}/results/${caseResult.case_id}`}>{caseResult.case_id.slice(0, 8)}</Link></td>
                    <td><EvaluationStatusBadge label={caseResult.hard_failure ? "hard failure" : caseResult.passed ? "passed" : "failed"} tone={toneForCase(caseResult.passed, caseResult.hard_failure)} /></td>
                    <td>{formatMs(caseResult.latency_ms)}</td>
                    <td>{caseResult.failure_reasons_json && caseResult.failure_reasons_json.length > 0 ? caseResult.failure_reasons_json.join(", ") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </section>
    </>
  );
}

async function loadRunDetail(session: DevelopmentDashboardSession, runId: string) {
  try {
    const [runDetail, results] = await Promise.all([getEvaluationRun(session, runId), listEvaluationRunResults(session, runId)]);
    const otherRunsResponse = await listEvaluationRuns(session, runDetail.data.run.dataset_id);
    const otherRuns = otherRunsResponse.data.filter((candidate) => candidate.id !== runId);
    return {
      ok: true as const,
      data: { run: runDetail.data.run, summary: runDetail.data.summary, gate: runDetail.data.gate, results: results.data, otherRuns },
    };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}

async function loadComparison(session: DevelopmentDashboardSession, baselineRunId: string, candidateRunId: string) {
  try {
    const response = await compareEvaluationRuns(session, baselineRunId, candidateRunId);
    return response.data;
  } catch {
    return null;
  }
}
