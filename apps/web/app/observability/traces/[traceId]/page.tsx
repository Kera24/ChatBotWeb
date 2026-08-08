import { AccessDeniedState, ErrorState } from "../../../../components/conversations/state-panels";
import { TraceDetailView } from "../../../../components/observability/trace-detail-view";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../../lib/api/errors";
import { getTraceDetail } from "../../../../lib/api/observability";
import type { DevelopmentDashboardSession } from "../../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../../lib/auth/session";

export const dynamic = "force-dynamic";

type TraceDetailPageProps = {
  params: Promise<{ traceId: string }>;
  searchParams: Promise<{ assistant?: string; include_content?: string }>;
};

export default async function TraceDetailPage({ params, searchParams }: TraceDetailPageProps) {
  const { traceId } = await params;
  const { assistant, include_content: includeContentParam } = await searchParams;
  const session = await requireDashboardSession();
  const includeContent = includeContentParam === "true";

  const result = await loadTraceDetail(session, traceId, { includeContent });
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    if (result.error.kind === "not_found") {
      return (
        <ErrorState
          message="This trace was not found for the current workspace. It may have expired past the retention window, or the link may be incorrect."
          retryHref={assistant ? `/observability?assistant=${assistant}` : "/observability"}
        />
      );
    }
    return <ErrorState message={messageForApiError(result.error)} retryHref={assistant ? `/observability?assistant=${assistant}` : "/observability"} />;
  }

  return <TraceDetailView trace={result.data} assistantId={assistant} includeContent={includeContent} />;
}

async function loadTraceDetail(session: DevelopmentDashboardSession, traceId: string, options: { includeContent: boolean }) {
  try {
    const response = await getTraceDetail(session, traceId, options);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
