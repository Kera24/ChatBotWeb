import { dashboardApiGet, dashboardApiPost } from "./client";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type PlanKey = "starter" | "professional" | "enterprise";

export type SubscriptionStatus =
  | "trialing"
  | "active"
  | "past_due"
  | "canceled"
  | "incomplete"
  | "incomplete_expired"
  | "unpaid"
  | "paused";

export type BillingPlan = {
  key: string;
  name: string;
  price_display: string;
  cadence: string;
  max_assistants: number | null;
  features: string[];
};

export type BillingUsage = {
  assistants_used: number;
  assistants_limit: number | null;
};

export type BillingSubscription = {
  organisation_id: string;
  plan_key: string;
  status: SubscriptionStatus | string;
  trial_ends_at: string | null;
  trial_days_remaining: number | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  canceled_at: string | null;
  has_payment_method: boolean;
  plan: BillingPlan;
  usage: BillingUsage;
};

export type BillingInvoice = {
  id: string;
  status: string;
  amount_due_cents: number;
  amount_paid_cents: number;
  currency: string;
  hosted_invoice_url: string | null;
  invoice_pdf_url: string | null;
  period_start: string | null;
  period_end: string | null;
  created_at: string;
};

export type CheckoutSessionResult = {
  checkout_url: string;
};

export type PortalSessionResult = {
  portal_url: string;
};

function billingPath(session: DevelopmentDashboardSession, suffix: string) {
  return `/api/v1/orgs/${session.organisationId}/billing${suffix}`;
}

export function getBillingSubscription(session: DevelopmentDashboardSession) {
  return dashboardApiGet<BillingSubscription>({
    path: billingPath(session, "/subscription"),
    session,
  });
}

export function listBillingInvoices(session: DevelopmentDashboardSession, limit = 50) {
  return dashboardApiGet<BillingInvoice[]>({
    path: billingPath(session, "/invoices"),
    session,
    searchParams: { limit },
  });
}

export function createCheckoutSession(session: DevelopmentDashboardSession, planKey: PlanKey | string) {
  return dashboardApiPost<CheckoutSessionResult>({
    path: billingPath(session, "/checkout-session"),
    session,
    body: { plan_key: planKey },
  });
}

export function createPortalSession(session: DevelopmentDashboardSession) {
  return dashboardApiPost<PortalSessionResult>({
    path: billingPath(session, "/portal-session"),
    session,
  });
}

export function cancelBillingSubscription(session: DevelopmentDashboardSession) {
  return dashboardApiPost<BillingSubscription>({
    path: billingPath(session, "/cancel"),
    session,
  });
}

export function resumeBillingSubscription(session: DevelopmentDashboardSession) {
  return dashboardApiPost<BillingSubscription>({
    path: billingPath(session, "/resume"),
    session,
  });
}

export type BillingData = {
  subscription: BillingSubscription;
  invoices: BillingInvoice[];
};

export async function loadBillingData(session: DevelopmentDashboardSession): Promise<BillingData> {
  const [subscription, invoices] = await Promise.all([
    getBillingSubscription(session),
    listBillingInvoices(session),
  ]);
  return { subscription: subscription.data, invoices: invoices.data };
}
