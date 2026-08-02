import { AccessDeniedState, ErrorState, MissingTenantConfiguration } from "../../components/conversations/state-panels";
import { SettingsDashboardClient } from "../../components/settings/settings-dashboard-client";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { getWorkspaceSettings } from "../../lib/api/settings";
import { getDevelopmentDashboardSession, type DevelopmentDashboardSession } from "../../lib/auth/development-session";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  const result = await loadSettings(tenant.session);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/settings" />;
  }

  return <SettingsDashboardClient session={tenant.session} initialSettings={result.data} />;
}

async function loadSettings(session: DevelopmentDashboardSession) {
  try {
    const response = await getWorkspaceSettings(session);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
