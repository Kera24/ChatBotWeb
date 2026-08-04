import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import type { BillingInvoice } from "../../lib/api/billing";
import { InvoiceHistory } from "./invoice-history";

function buildInvoice(overrides: Partial<BillingInvoice> = {}): BillingInvoice {
  return {
    id: "inv-1",
    status: "paid",
    amount_due_cents: 24900,
    amount_paid_cents: 24900,
    currency: "usd",
    hosted_invoice_url: "https://invoice.stripe.com/fake",
    invoice_pdf_url: "https://invoice.stripe.com/fake.pdf",
    period_start: "2026-01-01T00:00:00.000Z",
    period_end: "2026-02-01T00:00:00.000Z",
    created_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("InvoiceHistory", () => {
  it("shows an empty state when there are no invoices yet", () => {
    render(<InvoiceHistory invoices={[]} />);
    expect(screen.getByText("No invoices yet")).toBeTruthy();
  });

  it("renders invoice rows with formatted amount, status, and a link to the hosted invoice", () => {
    render(<InvoiceHistory invoices={[buildInvoice()]} />);
    expect(screen.getByText("$249.00")).toBeTruthy();
    expect(screen.getByText("paid")).toBeTruthy();
    expect(screen.getByRole("link", { name: "View invoice" }).getAttribute("href")).toBe("https://invoice.stripe.com/fake");
  });

  it("shows a placeholder when a hosted invoice link is not available", () => {
    render(<InvoiceHistory invoices={[buildInvoice({ hosted_invoice_url: null })]} />);
    expect(screen.getByText("Not available")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "View invoice" })).not.toBeInTheDocument();
  });
});
