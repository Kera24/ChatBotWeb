import { notFound } from "next/navigation";

import { AssistantDetailClient } from "../../../components/assistants/assistant-detail-client";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../lib/api/errors";
import { loadOverviewData } from "../../../lib/api/overview";
import {
  getWidgetDetail,
  getWidgetDraft,
  getWidgetEmbed,
  getWidgetInstallationStatus,
  listWidgetKnowledgeOptions,
  listWidgetOrigins,
  listWidgetRevisions,
  listWidgetSdkVersions,
} from "../../../lib/api/widgets";
import type { DevelopmentDashboardSession } from "../../../lib/auth/development-session";
import { requireDashboardSession } from "../../../lib/auth/session";
import { AccessDeniedState, ErrorState } from "../../../components/conversations/state-panels";

type AssistantDetailPageProps = {
  params: Promise<{ assistantId: string }>;
};

export const dynamic = "force-dynamic";

export default async function AssistantDetailPage({ params }: AssistantDetailPageProps) {
  const session = await requireDashboardSession();
  const { assistantId } = await params;
  const result = await loadAssistantDetail(session, assistantId);
  if (!result.ok) {
    if (result.error.kind === "not_found") notFound();
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref={`/assistants/${assistantId}`} />;
  }

  return <AssistantDetailClient session={session} {...result.data} />;
}

async function loadAssistantDetail(session: DevelopmentDashboardSession, assistantId: string) {
  try {
    const [widget, draft, origins, embed, sdkVersions, knowledgeOptions, revisions, installationStatus, overviewData] = await Promise.all([
      getWidgetDetail(session, assistantId),
      getWidgetDraft(session, assistantId),
      listWidgetOrigins(session, assistantId),
      getWidgetEmbed(session, assistantId),
      listWidgetSdkVersions(session),
      listWidgetKnowledgeOptions(session, assistantId),
      listWidgetRevisions(session, assistantId),
      getWidgetInstallationStatus(session, assistantId),
      loadOverviewData(session),
    ]);
    return {
      ok: true as const,
      data: {
        initialWidget: widget.data,
        initialDraft: draft.data,
        initialOrigins: origins.data,
        initialEmbed: embed.data,
        initialSdkVersions: sdkVersions.data,
        initialKnowledgeOptions: knowledgeOptions.data,
        initialRevisions: revisions.data,
        initialInstallationStatus: installationStatus.data,
        overviewData,
      },
    };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected assistant detail error.") };
  }
}
