import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { SettingsDashboardClient } from "../../components/settings/settings-dashboard-client";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { getWorkspaceSettings } from "../../lib/api/settings";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const session = await requireDashboardSession();

  const result = await loadSettings(session);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/settings" />;
  }

  return <SettingsDashboardClient session={session} initialSettings={result.data} />;
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
