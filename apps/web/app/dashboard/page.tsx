import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { AssistantManagement } from "../../components/assistants/assistant-management";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { loadOverviewData, type OverviewData } from "../../lib/api/overview";
import { getWidgetDetail, type WidgetDetail } from "../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

type AssistantDashboardData = {
  overview: OverviewData;
  assistants: WidgetDetail[];
};

export default async function DashboardPage() {
  const session = await requireDashboardSession();
  const result = await loadAssistantDashboard(session);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/dashboard" />;
  }

  return <AssistantManagement session={session} assistants={result.data.assistants} data={result.data.overview} />;
}

async function loadAssistantDashboard(session: DevelopmentDashboardSession) {
  try {
    const overview = await loadOverviewData(session);
    const assistants = await Promise.all(overview.widgets.map(async (widget) => (await getWidgetDetail(session, widget.id)).data));
    return { ok: true as const, data: { overview, assistants } satisfies AssistantDashboardData };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
