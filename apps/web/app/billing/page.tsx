import { AccessDeniedState, ErrorState } from "../../components/conversations/state-panels";
import { BillingDashboardClient } from "../../components/billing/billing-dashboard-client";
import { NoBillingRecordState } from "../../components/billing/billing-empty-states";
import { DashboardApiError, isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { loadBillingData, type BillingData } from "../../lib/api/billing";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { requireDashboardSession } from "../../lib/auth/session";

export const dynamic = "force-dynamic";

export default async function BillingPage() {
  const session = await requireDashboardSession();

  const result = await loadBilling(session);
  if (!result.ok) {
    if (result.error.kind === "forbidden") return <AccessDeniedState />;
    if (result.error.kind === "not_found") return <NoBillingRecordState />;
    return <ErrorState message={messageForApiError(result.error)} retryHref="/billing" />;
  }

  return <BillingDashboardClient session={session} initialBilling={result.data} />;
}

async function loadBilling(session: DevelopmentDashboardSession) {
  try {
    const data: BillingData = await loadBillingData(session);
    return { ok: true as const, data };
  } catch (error) {
    if (isDashboardApiError(error)) return { ok: false as const, error };
    return { ok: false as const, error: new DashboardApiError("unknown", "Unexpected billing error.") };
  }
}
