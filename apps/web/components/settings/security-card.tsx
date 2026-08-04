import { Lock } from "lucide-react";

import type { SettingsCapabilities, SettingsOperational } from "../../lib/api/settings";

export function SecurityCard({
  operational,
  capabilities,
  currentRole,
}: {
  operational: SettingsOperational;
  capabilities: SettingsCapabilities;
  currentRole: string;
}) {
  return (
    <section className="settingsPanel" aria-labelledby="security-settings-title">
      <div className="settingsPanelHeader">
        <div>
          <p className="sectionKicker">Security and audit</p>
          <h3 id="security-settings-title">Current access posture</h3>
        </div>
      </div>
      <dl className="settingsFacts">
        <div><dt>Current role</dt><dd>{roleLabel(currentRole)}</dd></div>
        <div><dt>Public widgets</dt><dd>{operational.public_widgets_enabled ? "Enabled" : "Disabled"}</dd></div>
        <div><dt>Public messages</dt><dd>{operational.public_widget_messages_enabled ? "Enabled" : "Disabled"}</dd></div>
        <div><dt>Pilot enforcement</dt><dd>{operational.public_widget_pilot_enforcement_enabled ? "Enabled" : "Disabled"}</dd></div>
        <div><dt>Service</dt><dd>{operational.service_name}</dd></div>
        <div><dt>Release</dt><dd>{operational.version}</dd></div>
        <div><dt>Phase</dt><dd>{operational.phase}</dd></div>
      </dl>

      {capabilities.secret_managed_fields.length > 0 ? (
        <div className="secretFieldBlock">
          <h4><Lock size={13} aria-hidden="true" />Environment-managed secrets</h4>
          <p className="reviewFilterNote">These values are stored securely outside the dashboard and are never fetched or displayed here.</p>
          <ul className="secretFieldList" aria-label="Environment-managed secret fields">
            {capabilities.secret_managed_fields.map((field) => (
              <li key={field} className="secretFieldChip"><Lock size={11} aria-hidden="true" />{formatCapability(field)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {capabilities.unsupported_fields.length > 0 ? (
        <div className="settingsCapabilityBlock">
          <h4>Not available in this dashboard</h4>
          <ul>
            {capabilities.unsupported_fields.map((field) => <li key={field}>{formatCapability(field)}</li>)}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function roleLabel(role: string) {
  return role.replace(/_/g, " ");
}

function formatCapability(value: string) {
  return value.replace(/_/g, " ").replace(/\./g, " / ");
}
