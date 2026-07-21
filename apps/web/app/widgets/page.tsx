import Link from "next/link";

import { AccessDeniedState, ErrorState, MissingTenantConfiguration } from "../../components/conversations/state-panels";
import { WidgetList } from "../../components/widgets/widget-status";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { listWidgets } from "../../lib/api/widgets";
import { getDevelopmentDashboardSession, type DevelopmentDashboardSession } from "../../lib/auth/development-session";

export const dynamic = "force-dynamic";

export default async function WidgetsPage() {
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  const result = await loadWidgets(tenant.session);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/widgets" />;
  }

  return (
    <section className="widgetAdminPage" aria-labelledby="widgets-title">
      <div className="widgetHero">
        <div>
          <p className="eyebrow">Widget administration</p>
          <h2 id="widgets-title">Website widgets</h2>
          <p>Manage saved draft settings, approved domains, public keys, and embed setup without publishing or changing pilot controls.</p>
        </div>
        <div className="widgetHeroAside">
          <strong>{result.data.length}</strong>
          <span>widgets in this workspace</span>
        </div>
      </div>

      <div className="conversationToolbar">
        <p className="mutedText">Public keys are shown only inside widget details and embed setup.</p>
        <Link className="actionButton" href="/widgets/new">Create widget</Link>
      </div>

      <WidgetList widgets={result.data} />
    </section>
  );
}

async function loadWidgets(session: DevelopmentDashboardSession) {
  try {
    const response = await listWidgets(session);
    return { ok: true as const, data: response.data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected dashboard error.") };
  }
}
