import { describe, expect, it, vi, beforeEach } from "vitest";

import { render, screen, userEvent, waitFor, within } from "../../test/test-utils";
import * as billingApi from "../../lib/api/billing";
import { DashboardApiError } from "../../lib/api/errors";
import type { BillingData, BillingSubscription } from "../../lib/api/billing";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { BillingDashboardClient } from "./billing-dashboard-client";

vi.mock("../../lib/api/billing");

function buildSubscription(overrides: Partial<BillingSubscription> = {}): BillingSubscription {
  return {
    organisation_id: "org-1",
    plan_key: "starter",
    status: "trialing",
    trial_ends_at: "2026-08-18T00:00:00.000Z",
    trial_days_remaining: 10,
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

function buildBilling(overrides: Partial<BillingData> = {}): BillingData {
  return { subscription: buildSubscription(), invoices: [], ...overrides };
}

function envelope<T>(data: T) {
  return { success: true, data, meta: {} };
}

const ownerSession: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "owner@example.test",
  fullName: "Owner User",
  role: "org_owner",
  onboardingComplete: true,
  organisationName: "Admissions College",
  workspaceName: "Admissions Workspace",
};

const viewerSession: DevelopmentDashboardSession = { ...ownerSession, role: "viewer" };

describe("BillingDashboardClient", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the header, metrics, plan picker, and invoice history", () => {
    render(<BillingDashboardClient session={ownerSession} initialBilling={buildBilling()} />);

    expect(screen.getByRole("heading", { name: "Billing" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Upgrade or downgrade your plan" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Past invoices" })).toBeTruthy();
    expect(screen.getByText("No invoices yet")).toBeTruthy();
  });

  function professionalUpgradeButton() {
    const card = screen.getByRole("heading", { name: "Professional" }).closest(".pricingCard") as HTMLElement;
    return within(card).getByRole("button", { name: /Upgrade|Redirecting/ });
  }

  it("starts checkout for the selected plan and shows a redirecting state", async () => {
    vi.mocked(billingApi.createCheckoutSession).mockImplementation(() => new Promise(() => {})); // never resolves, keeps pending state visible
    const user = userEvent.setup();
    render(<BillingDashboardClient session={ownerSession} initialBilling={buildBilling()} />);

    await user.click(professionalUpgradeButton());

    expect(billingApi.createCheckoutSession).toHaveBeenCalledWith(ownerSession, "professional");
    await waitFor(() => expect(screen.getByText(/Redirecting to checkout/)).toBeTruthy());
  });

  it("shows an error message when checkout cannot be started", async () => {
    vi.mocked(billingApi.createCheckoutSession).mockRejectedValue(new DashboardApiError("server", "Stripe is unavailable.", { status: 500 }));
    const user = userEvent.setup();
    render(<BillingDashboardClient session={ownerSession} initialBilling={buildBilling()} />);

    await user.click(professionalUpgradeButton());

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  });

  it("does not allow a viewer to change plans", () => {
    render(<BillingDashboardClient session={viewerSession} initialBilling={buildBilling()} />);
    expect(professionalUpgradeButton()).toBeDisabled();
  });

  it("opens a confirmation dialog before cancelling and cancels on confirm", async () => {
    const canceled = buildSubscription({ status: "active", has_payment_method: true, cancel_at_period_end: true });
    vi.mocked(billingApi.cancelBillingSubscription).mockResolvedValue(envelope(canceled));
    const user = userEvent.setup();
    render(<BillingDashboardClient session={ownerSession} initialBilling={buildBilling({ subscription: buildSubscription({ status: "active", has_payment_method: true }) })} />);

    await user.click(screen.getByRole("button", { name: "Cancel subscription" }));
    const dialog = screen.getByRole("dialog", { name: "Cancel your subscription?" });

    await user.click(within(dialog).getByRole("button", { name: "Cancel subscription" }));

    await waitFor(() => expect(billingApi.cancelBillingSubscription).toHaveBeenCalledWith(ownerSession));
    await waitFor(() => expect(screen.getByText(/will cancel at the end of the current billing period/)).toBeTruthy());
  });

  it("closes the cancel dialog without cancelling when the user keeps the subscription", async () => {
    const user = userEvent.setup();
    render(<BillingDashboardClient session={ownerSession} initialBilling={buildBilling({ subscription: buildSubscription({ status: "active", has_payment_method: true }) })} />);

    await user.click(screen.getByRole("button", { name: "Cancel subscription" }));
    await user.click(screen.getByRole("button", { name: "Keep subscription" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(billingApi.cancelBillingSubscription).not.toHaveBeenCalled();
  });

  it("resumes a subscription scheduled for cancellation", async () => {
    const resumed = buildSubscription({ status: "active", has_payment_method: true, cancel_at_period_end: false });
    vi.mocked(billingApi.resumeBillingSubscription).mockResolvedValue(envelope(resumed));
    const user = userEvent.setup();
    render(
      <BillingDashboardClient
        session={ownerSession}
        initialBilling={buildBilling({ subscription: buildSubscription({ status: "active", has_payment_method: true, cancel_at_period_end: true }) })}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Resume subscription" }));

    await waitFor(() => expect(billingApi.resumeBillingSubscription).toHaveBeenCalledWith(ownerSession));
    await waitFor(() => expect(screen.getByText("Your subscription has been resumed.")).toBeTruthy());
  });

  it("disables the billing portal button until a payment method is on file", () => {
    render(<BillingDashboardClient session={ownerSession} initialBilling={buildBilling()} />);
    expect(screen.getByRole("button", { name: "Open billing portal" })).toBeDisabled();
    expect(screen.getByText(/Start a paid plan to add a payment method/)).toBeTruthy();
  });
});
