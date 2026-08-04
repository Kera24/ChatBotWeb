import { CreditCard } from "lucide-react";
import Link from "next/link";

export function NoBillingRecordState() {
  return (
    <section className="settingsEmptyHero premiumEmptyState" role="status">
      <CreditCard size={30} aria-hidden="true" />
      <h2>Billing is not set up yet</h2>
      <p>We could not find a billing record for this organisation. Reload the page, or contact support if this keeps happening.</p>
      <div className="settingsEmptyHeroActions">
        <Link className="assistantAction primary" href="/billing">Reload billing</Link>
      </div>
    </section>
  );
}
