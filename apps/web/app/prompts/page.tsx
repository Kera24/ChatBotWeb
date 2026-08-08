import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { PromptsListView } from "../../components/prompts/prompts-list-view";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { listPromptTemplates } from "../../lib/api/prompts";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function PromptsPage() {
  const session = await requireDashboardSession();

  let result;
  try {
    const response = await listPromptTemplates(session);
    result = { ok: true as const, data: response.data };
  } catch (error) {
    result = { ok: false as const, error: isDashboardApiError(error) ? error : new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }

  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/prompts" />;
  }

  const canManage = session.role === "org_owner" || session.role === "client_admin" || session.role === "super_admin";

  return <PromptsListView session={session} templates={result.data} canManage={canManage} />;
}
