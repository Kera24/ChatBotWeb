import { NoAssistantSelectedState } from "../../../components/conversations/conversation-empty-states";
import { AccessDeniedState, ErrorState } from "../../../components/conversations/state-panels";
import { RegressionReportsView } from "../../../components/feedback-loop/regression-reports-view";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../lib/api/errors";
import { listRegressionReports, type EvaluationRegressionReport } from "../../../lib/api/feedback-loop";
import type { DevelopmentDashboardSession } from "../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../lib/auth/session";

export const dynamic = "force-dynamic";

type RegressionReportsPageProps = {
  searchParams: Promise<{ assistant?: string; dataset?: string }>;
};

export default async function RegressionReportsPage({ searchParams }: RegressionReportsPageProps) {
  const params = await searchParams;
  const session = await requireDashboardSession();
  if (!params.assistant) return <NoAssistantSelectedState />;

  const result = await loadReports(session, params.dataset);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/feedback-loop/regressions?assistant=${params.assistant}`} />;
  }

  return <RegressionReportsView reports={result.data} assistantId={params.assistant} />;
}

async function loadReports(session: DevelopmentDashboardSession, datasetId: string | undefined) {
  try {
    const response = await listRegressionReports(session, datasetId);
    return { ok: true as const, data: response.data as EvaluationRegressionReport[] };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
