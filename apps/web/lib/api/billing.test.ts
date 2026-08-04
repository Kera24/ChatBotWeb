import { describe, expect, it, vi } from "vitest";

import {
  cancelBillingSubscription,
  createCheckoutSession,
  createPortalSession,
  getBillingSubscription,
  listBillingInvoices,
  loadBillingData,
  resumeBillingSubscription,
} from "./billing";
import type { DevelopmentDashboardSession } from "../auth/development-session";

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  fullName: "Admin User",
  role: "org_owner",
  onboardingComplete: true,
  organisationName: "Admissions College",
  workspaceName: "Admissions Workspace",
};

function mockFetch(data: unknown = {}) {
  const mock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ success: true, data, meta: {} }), { status: 200 }));
  vi.stubGlobal("fetch", mock);
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");
  return mock;
}

describe("billing API helpers", () => {
  it("loads the organisation-scoped subscription", async () => {
    const mock = mockFetch({ plan_key: "starter" });

    await getBillingSubscription(session);

    const [url, init] = mock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/orgs/org-1/billing/subscription");
    expect(init.credentials).toBe("include");
  });

  it("lists invoices for the organisation with a bounded limit", async () => {
    const mock = mockFetch([]);

    await listBillingInvoices(session, 25);

    const [url] = mock.mock.calls[0];
    const parsed = new URL(String(url));
    expect(parsed.pathname).toBe("/api/v1/orgs/org-1/billing/invoices");
    expect(parsed.searchParams.get("limit")).toBe("25");
  });

  it("creates a checkout session for the requested plan", async () => {
    const mock = mockFetch({ checkout_url: "https://checkout.stripe.com/test" });

    await createCheckoutSession(session, "professional");

    const [url, init] = mock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/orgs/org-1/billing/checkout-session");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ plan_key: "professional" });
  });

  it("creates a customer portal session", async () => {
    const mock = mockFetch({ portal_url: "https://billing.stripe.com/test" });

    await createPortalSession(session);

    const [url, init] = mock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/orgs/org-1/billing/portal-session");
    expect(init.method).toBe("POST");
  });

  it("cancels the subscription", async () => {
    const mock = mockFetch({ cancel_at_period_end: true });

    await cancelBillingSubscription(session);

    const [url, init] = mock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/orgs/org-1/billing/cancel");
    expect(init.method).toBe("POST");
  });

  it("resumes the subscription", async () => {
    const mock = mockFetch({ cancel_at_period_end: false });

    await resumeBillingSubscription(session);

    const [url, init] = mock.mock.calls[0];
    expect(new URL(String(url)).pathname).toBe("/api/v1/orgs/org-1/billing/resume");
    expect(init.method).toBe("POST");
  });

  it("combines subscription and invoices into one payload", async () => {
    const mock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ success: true, data: { plan_key: "starter" }, meta: {} }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ success: true, data: [{ id: "inv-1" }], meta: {} }), { status: 200 }));
    vi.stubGlobal("fetch", mock);
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.local");

    const result = await loadBillingData(session);

    expect(result.subscription).toEqual({ plan_key: "starter" });
    expect(result.invoices).toEqual([{ id: "inv-1" }]);
  });
});
