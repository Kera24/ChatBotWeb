import { NoAssistantSelectedState } from "../../../components/conversations/conversation-empty-states";
import { AccessDeniedState, ErrorState } from "../../../components/conversations/state-panels";
import { DatasetVersionsView } from "../../../components/feedback-loop/dataset-versions-view";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../lib/api/errors";
import { listDatasetVersionEvents, type EvaluationDatasetVersionEvent } from "../../../lib/api/feedback-loop";
import type { DevelopmentDashboardSession } from "../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../lib/auth/session";

export const dynamic = "force-dynamic";

type DatasetVersionsPageProps = {
  searchParams: Promise<{ assistant?: string; dataset?: string }>;
};

export default async function DatasetVersionsPage({ searchParams }: DatasetVersionsPageProps) {
  const params = await searchParams;
  const session = await requireDashboardSession();
  if (!params.assistant) return <NoAssistantSelectedState />;

  const result = await loadEvents(session, params.dataset);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/feedback-loop/versions?assistant=${params.assistant}`} />;
  }

  return <DatasetVersionsView events={result.data} assistantId={params.assistant} />;
}

async function loadEvents(session: DevelopmentDashboardSession, datasetId: string | undefined) {
  try {
    const response = await listDatasetVersionEvents(session, datasetId);
    return { ok: true as const, data: response.data as EvaluationDatasetVersionEvent[] };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
