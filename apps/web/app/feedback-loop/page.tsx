import { NoAssistantSelectedState } from "../../components/conversations/conversation-empty-states";
import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { FeedbackLoopDashboard } from "../../components/feedback-loop/feedback-loop-dashboard";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { getFeedbackLoopMetrics, listEvaluationCandidates } from "../../lib/api/feedback-loop";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { getWidgetDetail } from "../../lib/api/widgets";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

type FeedbackLoopPageProps = {
  searchParams: Promise<{ assistant?: string; triage_status?: string; signal_type?: string; severity?: string }>;
};

export default async function FeedbackLoopPage({ searchParams }: FeedbackLoopPageProps) {
  const params = await searchParams;
  const session = await requireDashboardSession();
  if (!params.assistant) return <NoAssistantSelectedState />;

  const [candidatesResult, metricsResult, assistantResult] = await Promise.all([
    loadCandidates(session, params),
    loadMetrics(session, params.assistant),
    loadAssistant(session, params.assistant),
  ]);

  const retryHref = `/feedback-loop?assistant=${params.assistant}`;
  if (!candidatesResult.ok) return failureState(candidatesResult.error, retryHref);
  if (!metricsResult.ok) return failureState(metricsResult.error, retryHref);
  if (!assistantResult.ok) return failureState(assistantResult.error, retryHref);

  return (
    <FeedbackLoopDashboard
      assistant={assistantResult.data}
      candidates={candidatesResult.data}
      metrics={metricsResult.data}
      filters={{ triageStatus: params.triage_status, signalType: params.signal_type, severity: params.severity }}
      total={candidatesResult.meta.total}
    />
  );
}

function failureState(error: DashboardApiError, retryHref: string) {
  if (error.kind === "forbidden") return <AccessDeniedState />;
  return <ErrorState message={messageForApiError(error)} retryHref={retryHref} />;
}

async function loadCandidates(session: DevelopmentDashboardSession, params: { assistant?: string; triage_status?: string; signal_type?: string; severity?: string }) {
  try {
    const response = await listEvaluationCandidates(session, {
      widgetId: params.assistant,
      triage_status: params.triage_status,
      signal_type: params.signal_type,
      severity: params.severity,
    });
    return { ok: true as const, data: response.data, meta: response.meta ?? { limit: 50, offset: 0, count: response.data.length, total: response.data.length } };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}

async function loadMetrics(session: DevelopmentDashboardSession, assistantId: string) {
  try {
    const response = await getFeedbackLoopMetrics(session, assistantId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}

async function loadAssistant(session: DevelopmentDashboardSession, assistantId: string) {
  try {
    const response = await getWidgetDetail(session, assistantId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
