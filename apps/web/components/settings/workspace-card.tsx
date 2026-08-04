import { SaveBar } from "./save-bar";

export type WorkspaceFormState = {
  name: string;
  default_language: string;
};

export function WorkspaceCard({
  form,
  slug,
  updatedAt,
  canManage,
  dirty,
  saving,
  validationError,
  notice,
  error,
  isConflict,
  onFieldChange,
  onSave,
  onReset,
}: {
  form: WorkspaceFormState;
  slug: string;
  updatedAt: string;
  canManage: boolean;
  dirty: boolean;
  saving: boolean;
  validationError: string | null;
  notice: string | null;
  error: string | null;
  isConflict: boolean;
  onFieldChange: (field: keyof WorkspaceFormState, value: string) => void;
  onSave: () => void;
  onReset: () => void;
}) {
  return (
    <section className="settingsPanel settingsPrimaryPanel" aria-labelledby="workspace-settings-title">
      <div className="settingsPanelHeader">
        <div>
          <p className="sectionKicker">Workspace</p>
          <h3 id="workspace-settings-title">Editable workspace profile</h3>
        </div>
        <span className="settingsPanelBadge">{canManage ? "Editable" : "Read-only"}</span>
      </div>

      <form className="settingsForm" aria-label="Workspace settings" onSubmit={(event) => { event.preventDefault(); onSave(); }}>
        <label>
          Workspace name
          <input value={form.name} disabled={!canManage || saving} maxLength={255} onChange={(event) => onFieldChange("name", event.target.value)} />
        </label>
        <label>
          Default language
          <input value={form.default_language} disabled={!canManage || saving} maxLength={16} onChange={(event) => onFieldChange("default_language", event.target.value)} />
        </label>

        <dl className="settingsFacts">
          <div><dt>Workspace slug</dt><dd>{slug}</dd></div>
          <div><dt>Visibility</dt><dd>Private workspace</dd></div>
          <div><dt>Updated</dt><dd>{formatDateTime(updatedAt)}</dd></div>
        </dl>

        <SaveBar
          dirty={dirty}
          saving={saving}
          canManage={canManage}
          validationError={validationError}
          notice={notice}
          error={error}
          isConflict={isConflict}
          onSave={onSave}
          onReset={onReset}
        />
      </form>

      {!canManage ? <p className="mutedText">Your role can inspect settings, but only organisation owners and client admins can change workspace fields.</p> : null}
    </section>
  );
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
