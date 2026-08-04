import { AnalyticsDashboard, AnalyticsNoAssistantState } from "../../components/analytics/analytics-dashboard";
import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { loadAnalyticsData, type AnalyticsFilters } from "../../lib/api/analytics";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { getWidgetDetail } from "../../lib/api/widgets";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

type AnalyticsPageProps = {
  searchParams: Promise<{
    started_after?: string;
    started_before?: string;
    conversation_status?: string;
    conversation_channel?: string;
    document_status?: string;
    assistant?: string;
  }>;
};

export default async function AnalyticsPage({ searchParams }: AnalyticsPageProps) {
  const params = await searchParams;
  const session = await requireDashboardSession();
  if (!params.assistant) return <AnalyticsNoAssistantState />;

  const filters = normaliseFilters(params, params.assistant);
  const [result, assistantResult] = await Promise.all([loadAnalytics(session, filters), loadAssistant(session, params.assistant)]);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/analytics?assistant=${params.assistant}`} />;
  }
  if (!assistantResult.ok) {
    if (assistantResult.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(assistantResult.error)} retryHref={`/analytics?assistant=${params.assistant}`} />;
  }

  return <AnalyticsDashboard data={result.data} assistant={assistantResult.data} />;
}

async function loadAnalytics(session: DevelopmentDashboardSession, filters: AnalyticsFilters) {
  try {
    const data = await loadAnalyticsData(session, filters);
    return { ok: true as const, data };
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

function normaliseFilters(params: AnalyticsPageProps["searchParams"] extends Promise<infer T> ? T : never, assistantId: string): AnalyticsFilters {
  return {
    assistantId,
    started_after: dateParam(params.started_after),
    started_before: dateParam(params.started_before),
    conversation_status: enumParam(params.conversation_status, ["active", "completed", "abandoned", "archived"]),
    conversation_channel: enumParam(params.conversation_channel, ["dashboard_test", "widget", "api", "future_integration"]),
    document_status: enumParam(params.document_status, ["uploaded", "processing", "ready", "failed", "archived"]),
  };
}

function dateParam(value: string | undefined) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return undefined;
  return value;
}

function enumParam(value: string | undefined, allowed: string[]) {
  return value && allowed.includes(value) ? value : undefined;
}
