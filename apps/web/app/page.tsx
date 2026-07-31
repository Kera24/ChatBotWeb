import { AccessDeniedState, ErrorState, MissingTenantConfiguration } from "../components/conversations/state-panels";
import { OverviewDashboard } from "../components/overview/overview-dashboard";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../lib/api/errors";
import { loadOverviewData } from "../lib/api/overview";
import { getDevelopmentDashboardSession, type DevelopmentDashboardSession } from "../lib/auth/development-session";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  const result = await loadOverview(tenant.session);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/" />;
  }

  return (
    <OverviewDashboard
      session={tenant.session}
      data={result.data}
      environment={process.env.NEXT_PUBLIC_APP_ENV || process.env.NODE_ENV || "development"}
    />
  );
}

async function loadOverview(session: DevelopmentDashboardSession) {
  try {
    const data = await loadOverviewData(session);
    return { ok: true as const, data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
