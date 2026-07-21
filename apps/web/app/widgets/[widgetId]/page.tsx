import Link from "next/link";

import { AccessDeniedState, ErrorState, MissingTenantConfiguration } from "../../../components/conversations/state-panels";
import { WidgetDetailClient } from "../../../components/widgets/widget-detail-client";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../../lib/api/errors";
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
import { getDevelopmentDashboardSession, type DevelopmentDashboardSession } from "../../../lib/auth/development-session";

export const dynamic = "force-dynamic";

type WidgetDetailPageProps = {
  params: Promise<{ widgetId: string }>;
};

export default async function WidgetDetailPage({ params }: WidgetDetailPageProps) {
  const { widgetId } = await params;
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  const result = await loadWidgetAdminData(tenant.session, widgetId);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/widgets" />;
  }

  return (
    <>
      <Link className="backLink" href="/widgets">Back to widgets</Link>
      <WidgetDetailClient
        session={tenant.session}
        initialWidget={result.data.widget}
        initialDraft={result.data.draft}
        initialOrigins={result.data.origins}
        initialEmbed={result.data.embed}
        sdkVersions={result.data.sdkVersions}
        knowledgeOptions={result.data.knowledgeOptions}
        initialRevisions={result.data.revisions}
        initialInstallationStatus={result.data.installationStatus}
      />
    </>
  );
}

async function loadWidgetAdminData(session: DevelopmentDashboardSession, widgetId: string) {
  try {
    const [widget, draft, origins, embed, sdkVersions, knowledgeOptions, revisions, installationStatus] = await Promise.all([
      getWidgetDetail(session, widgetId),
      getWidgetDraft(session, widgetId),
      listWidgetOrigins(session, widgetId),
      getWidgetEmbed(session, widgetId),
      listWidgetSdkVersions(session),
      listWidgetKnowledgeOptions(session, widgetId),
      listWidgetRevisions(session, widgetId),
      getWidgetInstallationStatus(session, widgetId),
    ]);
    return {
      ok: true as const,
      data: {
        widget: widget.data,
        draft: draft.data,
        origins: origins.data,
        embed: embed.data,
        sdkVersions: sdkVersions.data,
        knowledgeOptions: knowledgeOptions.data,
        revisions: revisions.data,
        installationStatus: installationStatus.data,
      },
    };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
