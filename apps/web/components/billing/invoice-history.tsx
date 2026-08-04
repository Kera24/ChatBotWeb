import { FileText } from "lucide-react";

import type { BillingInvoice } from "../../lib/api/billing";

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}

function formatAmount(cents: number, currency: string) {
  return new Intl.NumberFormat("en", { style: "currency", currency: currency.toUpperCase() }).format(cents / 100);
}

const STATUS_TONE: Record<string, string> = {
  paid: "success",
  open: "warning",
  void: "neutral",
  uncollectible: "danger",
  draft: "neutral",
};

export function InvoiceHistory({ invoices }: { invoices: BillingInvoice[] }) {
  return (
    <section className="settingsPanel" aria-labelledby="invoice-history-title">
      <div className="settingsPanelHeader">
        <div>
          <p className="sectionKicker">Invoice history</p>
          <h3 id="invoice-history-title">Past invoices</h3>
        </div>
      </div>
      {invoices.length === 0 ? (
        <div className="overviewEmptyState">
          <FileText size={20} aria-hidden="true" />
          <h4>No invoices yet</h4>
          <p>Invoices appear here after your first billing cycle completes.</p>
        </div>
      ) : (
        <div className="premiumKnowledgeTable" style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Amount</th>
                <th scope="col">Status</th>
                <th scope="col">Invoice</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((invoice) => (
                <tr key={invoice.id}>
                  <td>{formatDate(invoice.created_at)}</td>
                  <td>{formatAmount(invoice.amount_paid_cents || invoice.amount_due_cents, invoice.currency)}</td>
                  <td>
                    <span className={`environmentBadge tone-${STATUS_TONE[invoice.status] ?? "neutral"}`}>{invoice.status}</span>
                  </td>
                  <td>
                    {invoice.hosted_invoice_url ? (
                      <a className="smallButton" href={invoice.hosted_invoice_url} target="_blank" rel="noreferrer noopener">
                        View invoice
                      </a>
                    ) : (
                      <span className="mutedText">Not available</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
