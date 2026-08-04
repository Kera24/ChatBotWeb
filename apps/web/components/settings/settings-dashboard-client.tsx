"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

import { isDashboardApiError, messageForApiError } from "../../lib/api/errors";
import { updateWorkspaceSettings, type WorkspaceSettings } from "../../lib/api/settings";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { AiConfigurationCard } from "./ai-configuration-card";
import { BrandingCard } from "./branding-card";
import { OrganisationCard } from "./organisation-card";
import { SecurityCard } from "./security-card";
import { SettingsHeader, type SaveState } from "./settings-header";
import { SettingsSummaryCards } from "./settings-summary-cards";
import { WorkspaceCard, type WorkspaceFormState } from "./workspace-card";

type SettingsDashboardClientProps = {
  session: DevelopmentDashboardSession;
  initialSettings: WorkspaceSettings;
};

const MANAGER_ROLES = new Set(["super_admin", "org_owner", "client_admin"]);

export function SettingsDashboardClient({ session, initialSettings }: SettingsDashboardClientProps) {
  const reduceMotion = useReducedMotion();
  const [settings, setSettings] = useState(initialSettings);
  const [form, setForm] = useState<WorkspaceFormState>({
    name: initialSettings.workspace.name,
    default_language: initialSettings.workspace.default_language,
  });
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConflict, setIsConflict] = useState(false);
  const canManage = MANAGER_ROLES.has(session.role);
  const dirty = form.name !== settings.workspace.name || form.default_language !== settings.workspace.default_language;
  const validationError = validateForm(form);

  const saveState: SaveState = saving ? "saving" : error ? "error" : notice ? "saved" : dirty ? "dirty" : "idle";

  useEffect(() => {
    if (!dirty) return undefined;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [dirty]);

  function updateField(field: keyof WorkspaceFormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setNotice(null);
    setError(null);
    setIsConflict(false);
  }

  function reset() {
    setForm({ name: settings.workspace.name, default_language: settings.workspace.default_language });
    setNotice(null);
    setError(null);
    setIsConflict(false);
  }

  async function save() {
    if (!canManage || validationError || !dirty) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    setIsConflict(false);
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
        if (caught.kind === "conflict") {
          setIsConflict(true);
          setError("These settings changed in another request. Reload the page before saving again.");
        } else {
          setError(messageForApiError(caught));
        }
      } else {
        setError("Workspace settings could not be saved.");
      }
    } finally {
      setSaving(false);
    }
  }

  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } };

  return (
    <motion.section className="settingsPage premiumSettingsPage" aria-labelledby="settings-title" {...pageMotion}>
      <SettingsHeader
        workspaceName={settings.workspace.name}
        organisationName={settings.organisation.name}
        planKey={settings.organisation.plan_key}
        environment={settings.operational.environment}
        saveState={saveState}
      />

      <SettingsSummaryCards
        data={{
          workspaceStatus: settings.workspace.status,
          language: settings.workspace.default_language,
          planKey: settings.organisation.plan_key,
          environment: settings.operational.environment,
          memberCount: settings.membership_summary.total,
        }}
      />

      <div className="settingsLayout">
        <WorkspaceCard
          form={form}
          slug={settings.workspace.slug}
          updatedAt={settings.workspace.updated_at}
          canManage={canManage}
          dirty={dirty}
          saving={saving}
          validationError={validationError}
          notice={notice}
          error={error}
          isConflict={isConflict}
          onFieldChange={updateField}
          onSave={() => void save()}
          onReset={reset}
        />
        <OrganisationCard organisation={settings.organisation} membershipSummary={settings.membership_summary} />
      </div>

      <div className="settingsLayout">
        <BrandingCard />
        <AiConfigurationCard operational={settings.operational} />
      </div>

      <div className="settingsLayout single">
        <SecurityCard operational={settings.operational} capabilities={settings.capabilities} currentRole={session.role} />
      </div>
    </motion.section>
  );
}

function validateForm(form: WorkspaceFormState) {
  if (form.name.trim().length === 0) return "Workspace name is required.";
  if (form.default_language.trim().length < 2) return "Default language must be at least two characters.";
  if (form.default_language.trim().length > 16) return "Default language must be 16 characters or fewer.";
  return null;
}
