"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useState } from "react";

import {
  cancelBillingSubscription,
  createCheckoutSession,
  createPortalSession,
  resumeBillingSubscription,
  type BillingData,
  type PlanKey,
} from "../../lib/api/billing";
import { DashboardApiError, messageForApiError } from "../../lib/api/errors";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { BillingHeader } from "./billing-header";
import { BillingMetrics } from "./billing-metrics";
import { InvoiceHistory } from "./invoice-history";
import { PlanPicker } from "./plan-picker";

const MANAGER_ROLES = new Set(["org_owner"]);

export function BillingDashboardClient({
  session,
  initialBilling,
}: {
  session: DevelopmentDashboardSession;
  initialBilling: BillingData;
}) {
  const reduceMotion = useReducedMotion();
  const [billing, setBilling] = useState(initialBilling);
  const [checkoutPending, setCheckoutPending] = useState<PlanKey | null>(null);
  const [portalPending, setPortalPending] = useState(false);
  const [cancelPending, setCancelPending] = useState(false);
  const [resumePending, setResumePending] = useState(false);
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canManage = MANAGER_ROLES.has(session.role);
  const { subscription, invoices } = billing;

  const pageMotion = reduceMotion
    ? { initial: false, animate: {} }
    : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } };

  async function handleSelectPlan(planKey: PlanKey) {
    if (planKey === subscription.plan_key || !canManage) return;
    setError(null);
    setNotice(null);
    setCheckoutPending(planKey);
    try {
      const result = await createCheckoutSession(session, planKey);
      window.location.href = result.data.checkout_url;
    } catch (caught) {
      setError(caught instanceof DashboardApiError ? messageForApiError(caught) : "Could not start checkout. Try again.");
      setCheckoutPending(null);
    }
  }

  async function handleOpenPortal() {
    setError(null);
    setNotice(null);
    setPortalPending(true);
    try {
      const result = await createPortalSession(session);
      window.location.href = result.data.portal_url;
    } catch (caught) {
      setError(caught instanceof DashboardApiError ? messageForApiError(caught) : "Could not open the billing portal. Try again.");
      setPortalPending(false);
    }
  }

  async function handleConfirmCancel() {
    setError(null);
    setCancelPending(true);
    try {
      const result = await cancelBillingSubscription(session);
      setBilling((current) => ({ ...current, subscription: result.data }));
      setNotice("Your subscription will cancel at the end of the current billing period.");
      setConfirmCancelOpen(false);
    } catch (caught) {
      setError(caught instanceof DashboardApiError ? messageForApiError(caught) : "Could not cancel the subscription. Try again.");
    } finally {
      setCancelPending(false);
    }
  }

  async function handleResume() {
    setError(null);
    setNotice(null);
    setResumePending(true);
    try {
      const result = await resumeBillingSubscription(session);
      setBilling((current) => ({ ...current, subscription: result.data }));
      setNotice("Your subscription has been resumed.");
    } catch (caught) {
      setError(caught instanceof DashboardApiError ? messageForApiError(caught) : "Could not resume the subscription. Try again.");
    } finally {
      setResumePending(false);
    }
  }

  return (
    <motion.section className="settingsPage premiumSettingsPage billingPage" aria-labelledby="billing-title" {...pageMotion}>
      <BillingHeader
        workspaceName={session.workspaceName}
        organisationName={session.organisationName}
        subscription={subscription}
      />

      {notice ? <p className="saveBarMessage saveBarSuccess" role="status">{notice}</p> : null}
      {error ? <p className="formError" role="alert">{error}</p> : null}

      <BillingMetrics subscription={subscription} />

      <div className="settingsLayout">
        <PlanPicker
          currentPlanKey={subscription.plan_key}
          pendingPlanKey={checkoutPending}
          canManage={canManage}
          onSelectPlan={handleSelectPlan}
        />

        <section className="settingsPanel" aria-labelledby="billing-actions-title">
          <div className="settingsPanelHeader">
            <div>
              <p className="sectionKicker">Manage subscription</p>
              <h3 id="billing-actions-title">Payment &amp; cancellation</h3>
            </div>
          </div>
          <dl className="settingsFacts compactFacts">
            <div>
              <dt>Payment method</dt>
              <dd>{subscription.has_payment_method ? "On file with Stripe" : "None on file yet"}</dd>
            </div>
          </dl>
          <div className="overviewActionList">
            <button type="button" className="smallButton" disabled={!subscription.has_payment_method || portalPending} onClick={() => void handleOpenPortal()}>
              {portalPending ? "Opening portal..." : "Open billing portal"}
            </button>
            {subscription.cancel_at_period_end ? (
              <button type="button" className="smallButton" disabled={resumePending} onClick={() => void handleResume()}>
                {resumePending ? "Resuming..." : "Resume subscription"}
              </button>
            ) : (
              <button
                type="button"
                className="smallButton dangerButton"
                disabled={!subscription.has_payment_method}
                onClick={() => setConfirmCancelOpen(true)}
              >
                Cancel subscription
              </button>
            )}
          </div>
          {!subscription.has_payment_method ? (
            <p className="reviewFilterNote">Start a paid plan to add a payment method and manage billing details.</p>
          ) : null}
        </section>
      </div>

      <InvoiceHistory invoices={invoices} />

      <AnimatePresence>
        {confirmCancelOpen ? (
          <div className="dialogBackdrop" role="presentation">
            <section className="confirmDialog" role="dialog" aria-modal="true" aria-labelledby="cancel-title" aria-describedby="cancel-description">
              <h2 id="cancel-title">Cancel your subscription?</h2>
              <p id="cancel-description">
                Your assistants stay active until the end of the current billing period ({subscription.current_period_end ?? "your renewal date"}).
                You can resume at any time before then.
              </p>
              <div className="formActions">
                <button className="actionButton" type="button" autoFocus onClick={() => setConfirmCancelOpen(false)} disabled={cancelPending}>
                  Keep subscription
                </button>
                <button className="actionButton dangerButton" type="button" disabled={cancelPending} onClick={() => void handleConfirmCancel()}>
                  {cancelPending ? "Cancelling..." : "Cancel subscription"}
                </button>
              </div>
            </section>
          </div>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
}
