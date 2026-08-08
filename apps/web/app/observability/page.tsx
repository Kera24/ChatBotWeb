import { NoAssistantSelectedState } from "../../components/conversations/conversation-empty-states";
import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { ObservabilityDashboard } from "../../components/observability/observability-dashboard";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { listAnomalies, listTraces, loadObservabilityMetrics } from "../../lib/api/observability";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { getWidgetDetail } from "../../lib/api/widgets";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

type ObservabilityPageProps = {
  searchParams: Promise<{
    assistant?: string;
    provider_key?: string;
    model_key?: string;
    answer_state?: string;
    status?: string;
    started_after?: string;
    started_before?: string;
  }>;
};

const RECENT_TRACES_LIMIT = 25;

export default async function ObservabilityPage({ searchParams }: ObservabilityPageProps) {
  const params = await searchParams;
  const session = await requireDashboardSession();
  if (!params.assistant) return <NoAssistantSelectedState />;

  const filters = {
    assistantId: params.assistant,
    provider_key: params.provider_key,
    model_key: params.model_key,
    answer_state: params.answer_state,
    status: params.status,
    started_after: dateParam(params.started_after),
    started_before: dateParam(params.started_before),
  };

  const [metricsResult, tracesResult, anomaliesResult, assistantResult] = await Promise.all([
    loadMetrics(session, filters),
    loadTraces(session, filters),
    loadAnomalies(session, { assistantId: params.assistant }),
    loadAssistant(session, params.assistant),
  ]);

  const retryHref = `/observability?assistant=${params.assistant}`;
  if (!metricsResult.ok) return failureState(metricsResult.error, retryHref);
  if (!tracesResult.ok) return failureState(tracesResult.error, retryHref);
  if (!anomaliesResult.ok) return failureState(anomaliesResult.error, retryHref);
  if (!assistantResult.ok) return failureState(assistantResult.error, retryHref);

  return (
    <ObservabilityDashboard
      assistant={assistantResult.data}
      metrics={metricsResult.data}
      traces={tracesResult.data}
      anomalies={anomaliesResult.data}
      filters={{ status: params.status, answerState: params.answer_state, providerKey: params.provider_key, modelKey: params.model_key }}
    />
  );
}

function failureState(error: DashboardApiError, retryHref: string) {
  if (error.kind === "forbidden") return <AccessDeniedState />;
  return <ErrorState message={messageForApiError(error)} retryHref={retryHref} />;
}

function dateParam(value: string | undefined) {
  if (!value) return undefined;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? undefined : value;
}

async function loadMetrics(session: DevelopmentDashboardSession, filters: Parameters<typeof loadObservabilityMetrics>[1]) {
  try {
    const response = await loadObservabilityMetrics(session, filters);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}

async function loadTraces(session: DevelopmentDashboardSession, filters: Parameters<typeof listTraces>[1]) {
  try {
    const response = await listTraces(session, { ...filters, limit: RECENT_TRACES_LIMIT, offset: 0 });
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}

async function loadAnomalies(session: DevelopmentDashboardSession, filters: Parameters<typeof listAnomalies>[1]) {
  try {
    const response = await listAnomalies(session, filters);
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
