import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { BillingSubscription } from "../../lib/api/billing";
import { BillingHeader } from "./billing-header";

function buildSubscription(overrides: Partial<BillingSubscription> = {}): BillingSubscription {
  return {
    organisation_id: "org-1",
    plan_key: "starter",
    status: "trialing",
    trial_ends_at: "2026-08-18T00:00:00.000Z",
    trial_days_remaining: 14,
    current_period_start: null,
    current_period_end: null,
    cancel_at_period_end: false,
    canceled_at: null,
    has_payment_method: false,
    plan: { key: "starter", name: "Starter", price_display: "$0", cadence: "to validate your first assistant", max_assistants: 1, features: ["1 assistant"] },
    usage: { assistants_used: 0, assistants_limit: 1 },
    ...overrides,
  };
}

describe("BillingHeader", () => {
  it("shows the workspace, organisation, and current plan", () => {
    render(<BillingHeader workspaceName="Admissions Workspace" organisationName="Admissions College" subscription={buildSubscription()} />);
    expect(screen.getByRole("heading", { name: "Billing" })).toBeTruthy();
    expect(screen.getByText(/Admissions College/)).toBeTruthy();
    expect(screen.getByText("Starter plan")).toBeTruthy();
  });

  it("shows a trial countdown while trialing", () => {
    render(<BillingHeader workspaceName="Workspace" organisationName="Org" subscription={buildSubscription({ trial_days_remaining: 5 })} />);
    expect(screen.getByText("5 days left in trial")).toBeTruthy();
  });

  it("hides the trial countdown once the subscription is active", () => {
    render(<BillingHeader workspaceName="Workspace" organisationName="Org" subscription={buildSubscription({ status: "active", trial_days_remaining: null })} />);
    expect(screen.queryByText(/left in trial/)).not.toBeInTheDocument();
  });

  it("communicates a pending cancellation without relying on colour alone", () => {
    render(<BillingHeader workspaceName="Workspace" organisationName="Org" subscription={buildSubscription({ status: "active", cancel_at_period_end: true, trial_days_remaining: null })} />);
    expect(screen.getByText(/cancels at period end/)).toBeTruthy();
  });

  it("labels a past-due subscription clearly", () => {
    render(<BillingHeader workspaceName="Workspace" organisationName="Org" subscription={buildSubscription({ status: "past_due", trial_days_remaining: null })} />);
    expect(screen.getByText("Payment past due")).toBeTruthy();
  });

  it("links to the pricing page and workspace settings", () => {
    render(<BillingHeader workspaceName="Workspace" organisationName="Org" subscription={buildSubscription()} />);
    const nav = screen.getByRole("navigation", { name: "Billing quick links" });
    expect(nav.querySelector('a[href="/pricing"]')).toBeTruthy();
    expect(nav.querySelector('a[href="/settings"]')).toBeTruthy();
  });
});
