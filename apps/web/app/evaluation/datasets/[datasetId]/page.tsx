import Link from "next/link";

import { AccessDeniedState, ErrorState } from "../../../../components/conversations/state-panels";
import { formatCategory, formatDateTime } from "../../../../components/evaluation/format";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../../lib/api/errors";
import { getEvaluationDataset } from "../../../../lib/api/evaluation";
import type { DevelopmentDashboardSession } from "../../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../../lib/auth/session";

export const dynamic = "force-dynamic";

type EvaluationDatasetPageProps = {
  params: Promise<{ datasetId: string }>;
};

export default async function EvaluationDatasetPage({ params }: EvaluationDatasetPageProps) {
  const { datasetId } = await params;
  const session = await requireDashboardSession();

  const result = await loadDataset(session, datasetId);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/evaluation" />;
  }

  const dataset = result.data;

  return (
    <>
      <Link className="backLink" href="/evaluation">Back to evaluation</Link>
      <section className="evaluationPage" aria-labelledby="evaluation-dataset-title">
        <div className="widgetHero">
          <div>
            <p className="eyebrow">Evaluation dataset</p>
            <h2 id="evaluation-dataset-title">{dataset.name}</h2>
            <p>{dataset.description || "No description provided."}</p>
          </div>
          <div className="widgetHeroAside">
            <strong>{dataset.cases.length}</strong>
            <span>case{dataset.cases.length === 1 ? "" : "s"}</span>
          </div>
        </div>

        <div className="widgetPanel">
          <h2>Details</h2>
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
              <dt>Assistant (widget) id</dt>
              <dd>{dataset.widget_id}</dd>
            </div>
            <div>
              <dt>Created</dt>
              <dd>{formatDateTime(dataset.created_at)}</dd>
            </div>
          </dl>
        </div>

        <section aria-labelledby="evaluation-dataset-cases-title">
          <p className="sectionKicker" id="evaluation-dataset-cases-title">Cases</p>
          {dataset.cases.length === 0 ? (
            <div className="statePanel">
              <p className="sectionKicker">No cases yet</p>
              <h2>This dataset has no cases</h2>
              <p>Add cases via the evaluation API before running this dataset.</p>
            </div>
          ) : (
            <div className="widgetList" role="list" aria-label="Evaluation cases">
              {dataset.cases.map((evaluationCase) => (
                <article className="widgetRow" role="listitem" key={evaluationCase.id}>
                  <div>
                    <p className="sectionKicker">{formatCategory(evaluationCase.category)}</p>
                    <h2>{evaluationCase.question}</h2>
                    {evaluationCase.reference_answer ? <p>Reference: {evaluationCase.reference_answer}</p> : null}
                  </div>
                  <dl className="widgetFacts">
                    <div>
                      <dt>Expected answerability</dt>
                      <dd>{formatCategory(evaluationCase.expected_answerability)}</dd>
                    </div>
                    <div>
                      <dt>Expected documents</dt>
                      <dd>{evaluationCase.expected_document_ids?.length ?? 0}</dd>
                    </div>
                    <div>
                      <dt>Tags</dt>
                      <dd>{evaluationCase.tags && evaluationCase.tags.length > 0 ? evaluationCase.tags.join(", ") : "—"}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </>
  );
}

async function loadDataset(session: DevelopmentDashboardSession, datasetId: string) {
  try {
    const response = await getEvaluationDataset(session, datasetId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
