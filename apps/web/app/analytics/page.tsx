import { AnalyticsDashboard } from "../../components/analytics/analytics-dashboard";
import { AccessDeniedState, ErrorState, MissingTenantConfiguration } from "../../components/conversations/state-panels";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { loadAnalyticsData, type AnalyticsFilters } from "../../lib/api/analytics";
import { getDevelopmentDashboardSession, type DevelopmentDashboardSession } from "../../lib/auth/development-session";

export const dynamic = "force-dynamic";

type AnalyticsPageProps = {
  searchParams: Promise<{
    started_after?: string;
    started_before?: string;
    conversation_status?: string;
    conversation_channel?: string;
    document_status?: string;
  }>;
};

export default async function AnalyticsPage({ searchParams }: AnalyticsPageProps) {
  const params = await searchParams;
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  const filters = normaliseFilters(params);
  const result = await loadAnalytics(tenant.session, filters);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/analytics" />;
  }

  return <AnalyticsDashboard data={result.data} />;
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

function normaliseFilters(params: AnalyticsPageProps["searchParams"] extends Promise<infer T> ? T : never): AnalyticsFilters {
  return {
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
