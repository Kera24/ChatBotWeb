import Link from "next/link";

import { WidgetCreateForm } from "../../../components/widgets/widget-create-form";
import { MissingTenantConfiguration } from "../../../components/conversations/state-panels";
import { getDevelopmentDashboardSession } from "../../../lib/auth/development-session";

export const dynamic = "force-dynamic";

export default function NewWidgetPage() {
  const tenant = getDevelopmentDashboardSession();

  if (!tenant.configured) {
    return <MissingTenantConfiguration missing={tenant.missing} invalid={tenant.invalid} />;
  }

  return (
    <section className="widgetAdminPage" aria-labelledby="new-widget-title">
      <Link className="backLink" href="/widgets">Back to widgets</Link>
      <div className="widgetHero">
        <div>
          <p className="eyebrow">Create widget</p>
          <h2 id="new-widget-title">Start a draft configuration</h2>
          <p>Creation produces a stable widget identity and an initial draft. It does not publish, pilot-enable, or deploy anything.</p>
        </div>
      </div>
      <section className="widgetPanel">
        <WidgetCreateForm session={tenant.session} />
      </section>
    </section>
  );
}
