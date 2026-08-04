import Link from "next/link";

import type { SettingsMembershipSummary, SettingsOrganisation } from "../../lib/api/settings";

export function OrganisationCard({ organisation, membershipSummary }: { organisation: SettingsOrganisation; membershipSummary: SettingsMembershipSummary }) {
  return (
    <section className="settingsPanel" aria-labelledby="organisation-settings-title">
      <div className="settingsPanelHeader">
        <div>
          <p className="sectionKicker">Organisation</p>
          <h3 id="organisation-settings-title">Read-only account context</h3>
        </div>
      </div>
      <dl className="settingsFacts">
        <div><dt>Name</dt><dd>{organisation.name}</dd></div>
        <div><dt>Slug</dt><dd>{organisation.slug}</dd></div>
        <div><dt>Status</dt><dd>{organisation.status}</dd></div>
        <div><dt>Plan</dt><dd>{organisation.plan_key}</dd></div>
        <div><dt>Access model</dt><dd>Role-based access</dd></div>
      </dl>
      <dl className="settingsFacts compactFacts settingsMembershipFacts">
        <div><dt>Total members</dt><dd>{membershipSummary.total}</dd></div>
        <div><dt>Active</dt><dd>{membershipSummary.active}</dd></div>
        <div><dt>Inactive</dt><dd>{membershipSummary.inactive}</dd></div>
        <div><dt>Administrators</dt><dd>{membershipSummary.administrators}</dd></div>
      </dl>
      <Link className="smallButton" href="/users">Manage access</Link>
    </section>
  );
}
