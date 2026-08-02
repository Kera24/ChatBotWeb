import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { KnowledgeBaseClient } from "../../components/knowledge/knowledge-base-client";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { listDocuments } from "../../lib/api/documents";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function KnowledgePage() {
  const session = await requireDashboardSession();

  const result = await loadDocuments(session);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/knowledge" />;
  }

  return <KnowledgeBaseClient session={session} initialDocuments={result.data} />;
}

async function loadDocuments(session: DevelopmentDashboardSession) {
  try {
    const response = await listDocuments(session);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
