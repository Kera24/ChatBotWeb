import Link from "next/link";

import { WidgetCreateForm } from "../../../components/widgets/widget-create-form";
import { requireDashboardSession } from "../../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function NewWidgetPage() {
  const session = await requireDashboardSession();

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
        <WidgetCreateForm session={session} />
      </section>
    </section>
  );
}
