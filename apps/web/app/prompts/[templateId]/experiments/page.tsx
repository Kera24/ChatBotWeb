import { AccessDeniedState, ErrorState } from "../../../../components/conversations/state-panels";
import { PromptExperimentsView } from "../../../../components/prompts/prompt-experiments-view";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../../lib/api/errors";
import { getPromptTemplate, listPromptVersions, type PromptLayer } from "../../../../lib/api/prompts";
import { listWidgets } from "../../../../lib/api/widgets";
import { requireDashboardSession } from "../../../../lib/auth/session";

export const dynamic = "force-dynamic";

type PromptExperimentsPageProps = {
  params: Promise<{ templateId: string }>;
};

export default async function PromptExperimentsPage({ params }: PromptExperimentsPageProps) {
  const { templateId } = await params;
  const session = await requireDashboardSession();

  const [templateResult, versionsResult, widgetsResult] = await Promise.all([
    safeLoad(() => getPromptTemplate(session, templateId)),
    safeLoad(() => listPromptVersions(session, templateId)),
    safeLoad(() => listWidgets(session)),
  ]);

  if (!templateResult.ok) return failureState(templateResult.error, "/prompts");
  if (!versionsResult.ok) return failureState(versionsResult.error, `/prompts/${templateId}`);

  const isSuperAdmin = session.role === "super_admin";
  const canManage = session.role === "org_owner" || session.role === "client_admin" || isSuperAdmin;
  const approvedOrLater = versionsResult.data.filter((version) => version.status !== "draft" && version.status !== "rejected");

  return (
    <PromptExperimentsView
      session={session}
      templateId={templateId}
      layer={templateResult.data.layer as PromptLayer}
      versions={approvedOrLater}
      widgets={widgetsResult.ok ? widgetsResult.data : []}
      canManage={canManage}
      isSuperAdmin={isSuperAdmin}
    />
  );
}

function failureState(error: DashboardApiError, retryHref: string) {
  if (error.kind === "forbidden") return <AccessDeniedState />;
  return <ErrorState message={messageForApiError(error)} retryHref={retryHref} />;
}

async function safeLoad<T>(loader: () => Promise<{ data: T }>): Promise<{ ok: true; data: T } | { ok: false; error: DashboardApiError }> {
  try {
    const response = await loader();
    return { ok: true, data: response.data };
  } catch (error) {
    return { ok: false, error: isDashboardApiError(error) ? error : new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
