import Link from "next/link";

import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { EvaluationStatusBadge } from "../../components/evaluation/badges";
import { formatDateTime, toneForRunStatus } from "../../components/evaluation/format";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { listEvaluationDatasets, listEvaluationRuns } from "../../lib/api/evaluation";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function EvaluationPage() {
  const session = await requireDashboardSession();

  const result = await loadEvaluationOverview(session);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/evaluation" />;
  }

  const { datasets, runs } = result.data;

  return (
    <section className="evaluationPage" aria-labelledby="evaluation-title">
      <div className="widgetHero">
        <div>
          <p className="eyebrow">Quality gate</p>
          <h2 id="evaluation-title">Evaluation</h2>
          <p>
            Inspect the datasets and runs that catch retrieval, answer, citation, and isolation regressions before
            launch. Automatic scoring here checks retrieval and safety behaviour against dataset expectations - it
            does not, on its own, prove an answer is factually correct.
          </p>
        </div>
        <div className="widgetHeroAside">
          <strong>{datasets.length}</strong>
          <span>evaluation dataset{datasets.length === 1 ? "" : "s"}</span>
        </div>
      </div>

      <section aria-labelledby="evaluation-datasets-title">
        <p className="sectionKicker" id="evaluation-datasets-title">Datasets</p>
        {datasets.length === 0 ? (
          <div className="statePanel">
            <p className="sectionKicker">No datasets yet</p>
            <h2>No evaluation datasets</h2>
            <p>Run <code>npm run eval:launch</code> to seed the sample launch dataset, or create one via the evaluation API.</p>
          </div>
        ) : (
          <div className="widgetList" role="list" aria-label="Evaluation datasets">
            {datasets.map((dataset) => (
              <article className="widgetRow" role="listitem" key={dataset.id}>
                <div>
                  <p className="sectionKicker">Dataset</p>
                  <h2><Link href={`/evaluation/datasets/${dataset.id}`}>{dataset.name}</Link></h2>
                  <p>{dataset.description || "No description provided."}</p>
                </div>
                <dl className="widgetFacts">
                  <div>
                    <dt>Version</dt>
                    <dd>{dataset.version}</dd>
                  </div>
                  <div>
                    <dt>Status</dt>
                    <dd>{dataset.status}</dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>{formatDateTime(dataset.created_at)}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="evaluation-runs-title">
        <p className="sectionKicker" id="evaluation-runs-title">Recent runs</p>
        {runs.length === 0 ? (
          <div className="statePanel">
            <p className="sectionKicker">No runs yet</p>
            <h2>No evaluation runs</h2>
            <p>Start one with <code>npm run eval:run -- --dataset &lt;id&gt; --assistant &lt;id&gt;</code>.</p>
          </div>
        ) : (
          <div className="widgetList" role="list" aria-label="Evaluation runs">
            {runs.map((run) => (
              <article className="widgetRow" role="listitem" key={run.id}>
                <div>
                  <p className="sectionKicker">Run · {run.mode}</p>
                  <h2><Link href={`/evaluation/runs/${run.id}`}>{run.id.slice(0, 8)}</Link></h2>
                  <p>Dataset version {run.dataset_version} · Model {run.model_key || "—"}</p>
                </div>
                <dl className="widgetFacts">
                  <div>
                    <dt>Status</dt>
                    <dd><EvaluationStatusBadge label={run.status} tone={toneForRunStatus(run.status)} /></dd>
                  </div>
                  <div>
                    <dt>Passed / total</dt>
                    <dd>{run.passed_cases} / {run.total_cases}</dd>
                  </div>
                  <div>
                    <dt>Hard failures</dt>
                    <dd>{run.hard_failure_cases}</dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>{formatDateTime(run.created_at)}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}

async function loadEvaluationOverview(session: DevelopmentDashboardSession) {
  try {
    const [datasets, runs] = await Promise.all([listEvaluationDatasets(session), listEvaluationRuns(session)]);
    return { ok: true as const, data: { datasets: datasets.data, runs: runs.data } };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
