import Link from "next/link";

import { AccessDeniedState, ErrorState } from "../../../../../../components/conversations/state-panels";
import { EvaluationStatusBadge } from "../../../../../../components/evaluation/badges";
import { formatCategory, formatMs, toneForCase } from "../../../../../../components/evaluation/format";
import { CreateCandidateLink } from "../../../../../../components/feedback-loop/create-candidate-link";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../../../../lib/api/errors";
import { getEvaluationRun, getEvaluationRunResult } from "../../../../../../lib/api/evaluation";
import type { DevelopmentDashboardSession } from "../../../../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../../../../lib/auth/session";

export const dynamic = "force-dynamic";

type EvaluationResultPageProps = {
  params: Promise<{ runId: string; caseId: string }>;
};

export default async function EvaluationResultPage({ params }: EvaluationResultPageProps) {
  const { runId, caseId } = await params;
  const session = await requireDashboardSession();

  const result = await loadResult(session, runId, caseId);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/evaluation/runs/${runId}`} />;
  }

  const { result: caseResult, case: evaluationCase } = result.data;
  const runResult = await loadRun(session, runId);
  const assistantId = runResult.ok ? runResult.data.run.widget_id : undefined;

  return (
    <>
      <Link className="backLink" href={`/evaluation/runs/${runId}`}>Back to run</Link>
      <section className="evaluationPage" aria-labelledby="evaluation-result-title">
        <div className="widgetHero">
          <div>
            <p className="eyebrow">{evaluationCase ? formatCategory(evaluationCase.category) : "Case"}</p>
            <h2 id="evaluation-result-title">{evaluationCase?.question || "Case result"}</h2>
            <p>{evaluationCase?.reference_answer ? `Reference: ${evaluationCase.reference_answer}` : "No reference answer recorded for this case."}</p>
          </div>
          <div className="widgetHeroAside">
            <EvaluationStatusBadge
              label={caseResult.hard_failure ? "hard failure" : caseResult.passed ? "passed" : "failed"}
              tone={toneForCase(caseResult.passed, caseResult.hard_failure)}
            />
            {!caseResult.passed && assistantId ? (
              <CreateCandidateLink
                sourceType="eval_result"
                assistantId={assistantId}
                prefillQuestion={evaluationCase?.question}
                prefillResponse={caseResult.actual_answer ?? undefined}
              />
            ) : null}
          </div>
        </div>

        {caseResult.failure_reasons_json && caseResult.failure_reasons_json.length > 0 ? (
          <div className="widgetPanel">
            <h2>Failure reasons</h2>
            <ul>
              {caseResult.failure_reasons_json.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {caseResult.error_message ? (
          <div className="widgetPanel">
            <h2>Error</h2>
            <p>{caseResult.error_message}</p>
          </div>
        ) : null}

        <div className="widgetPanel">
          <h2>Actual answer</h2>
          <p>{caseResult.actual_answer || "No answer was produced."}</p>
          <dl className="widgetFacts">
            <div><dt>Answer state</dt><dd>{caseResult.answer_state || "—"}</dd></div>
            <div><dt>Latency</dt><dd>{formatMs(caseResult.latency_ms)}</dd></div>
            <div><dt>Total tokens</dt><dd>{caseResult.total_tokens ?? "—"}</dd></div>
          </dl>
        </div>

        {caseResult.retrieval_metrics_json ? (
          <div className="widgetPanel">
            <h2>Retrieval metrics</h2>
            <dl className="widgetFacts">
              {Object.entries(caseResult.retrieval_metrics_json).map(([key, value]) => (
                <div key={key}>
                  <dt>{formatCategory(key)}</dt>
                  <dd>{formatMetricValue(value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}

        {caseResult.answer_metrics_json ? (
          <div className="widgetPanel">
            <h2>Answer &amp; safety metrics</h2>
            <dl className="widgetFacts">
              {Object.entries(caseResult.answer_metrics_json).map(([key, value]) => (
                <div key={key}>
                  <dt>{formatCategory(key)}</dt>
                  <dd>{formatMetricValue(value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}

        {caseResult.judge_scores_json ? (
          <div className="widgetPanel">
            <h2>Model-as-judge scores (estimates, not ground truth)</h2>
            <dl className="widgetFacts">
              {Object.entries(caseResult.judge_scores_json).map(([key, value]) => (
                <div key={key}>
                  <dt>{formatCategory(key)}</dt>
                  <dd>{formatMetricValue(value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}
      </section>
    </>
  );
}

function formatMetricValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value);
}

async function loadResult(session: DevelopmentDashboardSession, runId: string, caseId: string) {
  try {
    const response = await getEvaluationRunResult(session, runId, caseId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}

async function loadRun(session: DevelopmentDashboardSession, runId: string) {
  try {
    const response = await getEvaluationRun(session, runId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
