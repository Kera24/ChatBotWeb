import { Building2 } from "lucide-react";
import Link from "next/link";

export function WorkspaceMissingState() {
  return (
    <section className="settingsEmptyHero premiumEmptyState" role="status">
      <Building2 size={26} aria-hidden="true" />
      <h2>Workspace not found</h2>
      <p>This workspace could not be found. It may have been removed, or the link may be incorrect.</p>
      <div className="settingsEmptyHeroActions">
        <Link className="assistantAction primary" href="/dashboard">Go to My Assistants</Link>
      </div>
    </section>
  );
}
