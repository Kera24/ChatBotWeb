import { AlertTriangle, CheckCircle2, Clock3, XCircle } from "lucide-react";
import Link from "next/link";

import type { BillingSubscription } from "../../lib/api/billing";

const STATUS_TONE: Record<string, string> = {
  trialing: "info",
  active: "success",
  past_due: "warning",
  unpaid: "danger",
  incomplete: "warning",
  incomplete_expired: "danger",
  canceled: "danger",
  paused: "neutral",
};

const STATUS_LABEL: Record<string, string> = {
  trialing: "Free trial",
  active: "Active",
  past_due: "Payment past due",
  unpaid: "Unpaid",
  incomplete: "Incomplete",
  incomplete_expired: "Trial expired",
  canceled: "Canceled",
  paused: "Paused",
};

export function BillingHeader({
  workspaceName,
  organisationName,
  subscription,
}: {
  workspaceName: string;
  organisationName: string;
  subscription: BillingSubscription;
}) {
  return (
    <header className="premiumSettingsHero">
      <div className="settingsHeroMain">
        <div>
          <p className="eyebrow">Billing &amp; subscription</p>
          <h2 id="billing-title">Billing</h2>
          <p>Manage {organisationName}&rsquo;s plan, trial, and invoices for {workspaceName}.</p>
          <div className="settingsHeroMeta" aria-label="Billing status summary">
            <PlanBadge plan={subscription.plan} />
            <StatusBadge status={subscription.status} cancelAtPeriodEnd={subscription.cancel_at_period_end} />
            <TrialCountdown subscription={subscription} />
          </div>
        </div>
      </div>
      <nav className="settingsQuickLinks" aria-label="Billing quick links">
        <Link href="/pricing">View all plans</Link>
        <Link href="/settings">Workspace settings</Link>
      </nav>
    </header>
  );
}

export function PlanBadge({ plan }: { plan: BillingSubscription["plan"] }) {
  return (
    <span className="environmentBadge tone-info" aria-label={`Current plan: ${plan.name}`}>
      {plan.name} plan
    </span>
  );
}

function StatusBadge({ status, cancelAtPeriodEnd }: { status: string; cancelAtPeriodEnd: boolean }) {
  const tone = STATUS_TONE[status] ?? "neutral";
  const label = STATUS_LABEL[status] ?? status.replace(/_/g, " ");
  const Icon = tone === "success" ? CheckCircle2 : tone === "danger" ? XCircle : tone === "warning" ? AlertTriangle : Clock3;
  const suffix = cancelAtPeriodEnd && status !== "canceled" ? " · cancels at period end" : "";
  return (
    <span className={`environmentBadge tone-${tone}`} role="status">
      <Icon size={13} aria-hidden="true" />
      {label}
      {suffix}
    </span>
  );
}

export function TrialCountdown({ subscription }: { subscription: BillingSubscription }) {
  if (subscription.status !== "trialing" || subscription.trial_days_remaining === null) return null;
  const days = subscription.trial_days_remaining;
  const tone = days <= 3 ? "danger" : days <= 7 ? "warning" : "info";
  const label = days === 0 ? "Trial ends today" : days === 1 ? "1 day left in trial" : `${days} days left in trial`;
  return (
    <span className={`environmentBadge tone-${tone}`} role="status">
      <Clock3 size={13} aria-hidden="true" />
      {label}
    </span>
  );
}
