import { AccessDeniedState, ErrorState, MissingTenantConfiguration } from "../../components/conversations/state-panels";
import { UsersManagementClient } from "../../components/users/users-management-client";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { listMemberships } from "../../lib/api/users";
import { getDevelopmentDashboardSession, type DevelopmentDashboardSession } from "../../lib/auth/development-session";

export const dynamic = "force-dynamic";

export default async function UsersPage() {
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  const result = await loadMemberships(tenant.session);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/users" />;
  }

  return <UsersManagementClient session={tenant.session} initialMemberships={result.data} meta={result.meta} />;
}

async function loadMemberships(session: DevelopmentDashboardSession) {
  try {
    const response = await listMemberships(session);
    return { ok: true as const, data: response.data, meta: response.meta ?? { count: response.data.length, roles: [], statuses: [] } };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
