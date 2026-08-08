import { NoAssistantSelectedState } from "../../../components/conversations/conversation-empty-states";
import { AccessDeniedState, ErrorState } from "../../../components/conversations/state-panels";
import { ScheduledRunsView } from "../../../components/feedback-loop/scheduled-runs-view";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../lib/api/errors";
import { listEvaluationRuns, type EvaluationRun } from "../../../lib/api/evaluation";
import type { DevelopmentDashboardSession } from "../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../lib/auth/session";

export const dynamic = "force-dynamic";

type ScheduledRunsPageProps = {
  searchParams: Promise<{ assistant?: string; dataset?: string }>;
};

export default async function ScheduledRunsPage({ searchParams }: ScheduledRunsPageProps) {
  const params = await searchParams;
  const session = await requireDashboardSession();
  if (!params.assistant) return <NoAssistantSelectedState />;

  const result = await loadRuns(session, params.dataset);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/feedback-loop/runs?assistant=${params.assistant}`} />;
  }

  return <ScheduledRunsView runs={result.data} assistantId={params.assistant} />;
}

async function loadRuns(session: DevelopmentDashboardSession, datasetId: string | undefined) {
  try {
    const response = await listEvaluationRuns(session, datasetId);
    return { ok: true as const, data: response.data as EvaluationRun[] };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
