import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { KnowledgeBaseClient } from "../../components/knowledge/knowledge-base-client";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { listDocuments } from "../../lib/api/documents";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

type KnowledgePageProps = {
  searchParams: Promise<{ assistant?: string }>;
};

export default async function KnowledgePage({ searchParams }: KnowledgePageProps) {
  const params = await searchParams;
  const session = await requireDashboardSession();
  if (!params.assistant) return <ErrorState message="Select an assistant before managing knowledge." retryHref="/dashboard" />;

  const result = await loadDocuments(session, params.assistant);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/knowledge?assistant=${params.assistant}`} />;
  }

  return <KnowledgeBaseClient session={session} assistantId={params.assistant} initialDocuments={result.data} />;
}

async function loadDocuments(session: DevelopmentDashboardSession, assistantId: string) {
  try {
    const response = await listDocuments(session, assistantId);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}