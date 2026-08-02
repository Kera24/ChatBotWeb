"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { updateWorkspaceSettings, type WorkspaceSettings } from "../../lib/api/settings";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type SettingsDashboardClientProps = {
  session: DevelopmentDashboardSession;
  initialSettings: WorkspaceSettings;
};

type FormState = {
  name: string;
  default_language: string;
};

const MANAGER_ROLES = new Set(["super_admin", "org_owner", "client_admin"]);

export function SettingsDashboardClient({ session, initialSettings }: SettingsDashboardClientProps) {
  const [settings, setSettings] = useState(initialSettings);
  const [form, setForm] = useState<FormState>({
    name: initialSettings.workspace.name,
    default_language: initialSettings.workspace.default_language,
  });
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canManage = MANAGER_ROLES.has(session.role);
  const dirty = form.name !== settings.workspace.name || form.default_language !== settings.workspace.default_language;
  const validationError = validateForm(form);

  const membershipCards = useMemo(() => [
    { label: "Members", value: settings.membership_summary.total, detail: "Organisation memberships." },
    { label: "Active", value: settings.membership_summary.active, detail: "Memberships allowed by RBAC." },
    { label: "Inactive", value: settings.membership_summary.inactive, detail: "Memberships blocked from access." },
    { label: "Administrators", value: settings.membership_summary.administrators, detail: "Owners and client admins." },
  ], [settings.membership_summary]);

  useEffect(() => {
    if (!dirty) return undefined;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  function updateField(field: keyof FormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setNotice(null);
    setError(null);
  }

  function reset() {
    setForm({ name: settings.workspace.name, default_language: settings.workspace.default_language });
    setNotice(null);
    setError(null);
  }

  async function save() {
    if (!canManage || validationError || !dirty) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const response = await updateWorkspaceSettings(session, {
        name: form.name.trim(),
        default_language: form.default_language.trim(),
        expected_updated_at: settings.workspace.updated_at,
      });
      setSettings(response.data);
      setForm({ name: response.data.workspace.name, default_language: response.data.workspace.default_language });
      setNotice("Workspace settings saved.");
    } catch (caught) {
      if (isDashboardApiError(caught)) {
        setError(caught.kind === "conflict" ? "These settings changed in another request. Reload the page before saving again." : messageForApiError(caught));
      } else {
        setError("Workspace settings could not be saved.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="settingsPage" aria-labelledby="settings-title">
      <div className="settingsHero">
        <div>
          <p className="eyebrow">Yuranix settings</p>
          <h2 id="settings-title">Workspace controls and operational posture</h2>
          <p>Manage the settings that are persisted for this workspace and inspect read-only platform configuration without exposing secrets.</p>
        </div>
        <div className="settingsHeroAside">
          <strong>{settings.workspace.status}</strong>
          <span>{settings.operational.environment} environment</span>
        </div>
      </div>

      <section className="settingsMetricGrid" aria-label="Access metrics">
        {membershipCards.map((card) => <MetricCard key={card.label} {...card} />)}
      </section>

      {notice ? <div className="widgetNotice" role="status">{notice}</div> : null}
      {error ? <div className="statePanel urgentState" role="alert"><h2>Settings update failed</h2><p>{error}</p></div> : null}

      <div className="settingsLayout">
        <section className="settingsPanel settingsPrimaryPanel" aria-labelledby="workspace-settings-title">
          <div className="settingsPanelHeader">
            <div>
              <p className="sectionKicker">Workspace</p>
              <h3 id="workspace-settings-title">Editable workspace profile</h3>
            </div>
            <span>{canManage ? "Editable" : "Read-only"}</span>
          </div>
          <form className="settingsForm" aria-label="Workspace settings" onSubmit={(event) => { event.preventDefault(); void save(); }}>
            <label>
              Workspace name
              <input value={form.name} disabled={!canManage || saving} maxLength={255} onChange={(event) => updateField("name", event.target.value)} />
            </label>
            <label>
              Default language
              <input value={form.default_language} disabled={!canManage || saving} maxLength={16} onChange={(event) => updateField("default_language", event.target.value)} />
            </label>
            {validationError ? <p className="formError" role="alert">{validationError}</p> : null}
            <dl className="settingsFacts">
              <div><dt>Workspace slug</dt><dd>{settings.workspace.slug}</dd></div>
              <div><dt>Visibility</dt><dd>Private workspace</dd></div>
              <div><dt>Updated</dt><dd>{formatDateTime(settings.workspace.updated_at)}</dd></div>
            </dl>
            <div className="formActions">
              <button className="actionButton" type="submit" disabled={!canManage || !dirty || Boolean(validationError) || saving}>{saving ? "Saving" : "Save changes"}</button>
              <button className="smallButton" type="button" disabled={!dirty || saving} onClick={reset}>Reset</button>
            </div>
          </form>
          {!canManage ? <p className="mutedText">Your role can inspect settings, but only organisation owners and client admins can change workspace fields.</p> : null}
        </section>

        <section className="settingsPanel" aria-labelledby="organisation-settings-title">
          <div className="settingsPanelHeader">
            <div>
              <p className="sectionKicker">Organisation</p>
              <h3 id="organisation-settings-title">Read-only account context</h3>
            </div>
          </div>
          <dl className="settingsFacts">
            <div><dt>Name</dt><dd>{settings.organisation.name}</dd></div>
            <div><dt>Slug</dt><dd>{settings.organisation.slug}</dd></div>
            <div><dt>Status</dt><dd>{settings.organisation.status}</dd></div>
            <div><dt>Plan</dt><dd>{settings.organisation.plan_key}</dd></div>
            <div><dt>Access model</dt><dd>Role-based access</dd></div>
          </dl>
          <Link className="smallButton" href="/users">Manage access</Link>
        </section>
      </div>

      <div className="settingsLayout">
        <section className="settingsPanel" aria-labelledby="branding-settings-title">
          <div className="settingsPanelHeader">
            <div>
              <p className="sectionKicker">Branding and chatbot</p>
              <h3 id="branding-settings-title">Widget-owned configuration</h3>
            </div>
          </div>
          <p>Client-facing chatbot name, colours, logo, welcome message, fallback contact, privacy links, suggestions, citations, and conversation behaviour are stored per widget.</p>
          <div className="settingsLinkList">
            <Link className="smallButton" href="/widgets">Manage widget configuration</Link>
            <Link className="smallButton" href="/chatbot">Open chatbot preview</Link>
          </div>
        </section>

        <section className="settingsPanel" aria-labelledby="ai-settings-title">
          <div className="settingsPanelHeader">
            <div>
              <p className="sectionKicker">AI and retrieval</p>
              <h3 id="ai-settings-title">Environment-controlled configuration</h3>
            </div>
          </div>
          <dl className="settingsFacts compactFacts">
            <div><dt>Provider</dt><dd>{settings.operational.default_ai_provider_key}</dd></div>
            <div><dt>Model</dt><dd>{settings.operational.default_ai_model_key}</dd></div>
            <div><dt>Embedding provider</dt><dd>{settings.operational.embedding_provider}</dd></div>
            <div><dt>Embedding model</dt><dd>{settings.operational.embedding_model}</dd></div>
            <div><dt>Embedding dimension</dt><dd>{settings.operational.embedding_dimension}</dd></div>
            <div><dt>Top context chunks</dt><dd>{settings.operational.retrieval_max_context_chunks}</dd></div>
            <div><dt>Context character cap</dt><dd>{settings.operational.retrieval_max_context_chars}</dd></div>
            <div><dt>Chunk size</dt><dd>{settings.operational.chunk_size_words} words</dd></div>
            <div><dt>Chunk overlap</dt><dd>{settings.operational.chunk_overlap_words} words</dd></div>
            <div><dt>Request timeout</dt><dd>{settings.operational.ai_request_timeout_seconds}s</dd></div>
          </dl>
        </section>
      </div>

      <div className="settingsLayout">
        <section className="settingsPanel" aria-labelledby="security-settings-title">
          <div className="settingsPanelHeader">
            <div>
              <p className="sectionKicker">Security and audit</p>
              <h3 id="security-settings-title">Current access posture</h3>
            </div>
          </div>
          <dl className="settingsFacts">
            <div><dt>Current role</dt><dd>{roleLabel(session.role)}</dd></div>
            <div><dt>Public widgets</dt><dd>{settings.operational.public_widgets_enabled ? "Enabled" : "Disabled"}</dd></div>
            <div><dt>Public messages</dt><dd>{settings.operational.public_widget_messages_enabled ? "Enabled" : "Disabled"}</dd></div>
            <div><dt>Pilot enforcement</dt><dd>{settings.operational.public_widget_pilot_enforcement_enabled ? "Enabled" : "Disabled"}</dd></div>
            <div><dt>Service</dt><dd>{settings.operational.service_name}</dd></div>
            <div><dt>Release</dt><dd>{settings.operational.version}</dd></div>
            <div><dt>Phase</dt><dd>{settings.operational.phase}</dd></div>
          </dl>
        </section>

        <section className="settingsPanel" aria-labelledby="advanced-settings-title">
          <div className="settingsPanelHeader">
            <div>
              <p className="sectionKicker">Advanced</p>
              <h3 id="advanced-settings-title">Supported boundaries</h3>
            </div>
          </div>
          <CapabilityList title="Editable" items={settings.capabilities.editable_fields} />
          <CapabilityList title="Secret-managed" items={settings.capabilities.secret_managed_fields} />
          <CapabilityList title="Unsupported here" items={settings.capabilities.unsupported_fields} />
        </section>
      </div>
    </section>
  );
}

export function SettingsSkeleton() {
  return (
    <section className="settingsPage" aria-busy="true" aria-live="polite">
      <div className="settingsHero settingsSkeletonBlock">
        <div>
          <p className="eyebrow">Loading</p>
          <h2>Loading Yuranix settings</h2>
          <p>Collecting tenant-scoped workspace and operational configuration.</p>
        </div>
      </div>
      <div className="settingsMetricGrid">
        {[0, 1, 2, 3].map((item) => <div className="settingsMetricCard settingsSkeletonBlock" key={item} />)}
      </div>
    </section>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: number; detail: string }) {
  return <article className="settingsMetricCard"><span>{label}</span><strong>{value}</strong><p>{detail}</p></article>;
}

function CapabilityList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="settingsCapabilityBlock">
      <h4>{title}</h4>
      <ul>
        {items.map((item) => <li key={item}>{formatCapability(item)}</li>)}
      </ul>
    </div>
  );
}

function validateForm(form: FormState) {
  if (form.name.trim().length === 0) return "Workspace name is required.";
  if (form.default_language.trim().length < 2) return "Default language must be at least two characters.";
  if (form.default_language.trim().length > 16) return "Default language must be 16 characters or fewer.";
  return null;
}

function roleLabel(role: string) {
  return role.replace(/_/g, " ");
}

function formatCapability(value: string) {
  return value.replace(/_/g, " ").replace(/\./g, " / ");
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}


