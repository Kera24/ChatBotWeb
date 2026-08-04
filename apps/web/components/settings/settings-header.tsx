import { CheckCircle2, Loader2, MessageSquare, PenSquare, Rocket, Users as UsersIcon } from "lucide-react";
import Link from "next/link";

export type SaveState = "idle" | "dirty" | "saving" | "saved" | "error";

const ENVIRONMENT_TONE: Record<string, string> = {
  production: "danger",
  staging: "warning",
  development: "info",
};

export function SettingsHeader({
  workspaceName,
  organisationName,
  planKey,
  environment,
  saveState,
}: {
  workspaceName: string;
  organisationName: string;
  planKey: string;
  environment: string;
  saveState: SaveState;
}) {
  const environmentTone = ENVIRONMENT_TONE[environment] ?? "neutral";

  return (
    <header className="premiumSettingsHero">
      <div className="settingsHeroMain">
        <div>
          <p className="eyebrow">Workspace configuration</p>
          <h2 id="settings-title">Workspace Settings</h2>
          <p>Manage {workspaceName}&rsquo;s persisted settings and inspect read-only operational configuration for {organisationName}.</p>
          <div className="settingsHeroMeta" aria-label="Workspace and environment summary">
            <span className={`environmentBadge tone-${environmentTone}`}>{environment} environment</span>
            <span>{organisationName} · {planKey} plan</span>
            <SaveStateIndicator state={saveState} />
          </div>
        </div>
      </div>
      <nav className="settingsQuickLinks" aria-label="Workspace quick links">
        <Link href="/users"><UsersIcon size={15} aria-hidden="true" />Members</Link>
        <Link href="/widgets"><Rocket size={15} aria-hidden="true" />Widget Builder</Link>
        <Link href="/chatbot"><MessageSquare size={15} aria-hidden="true" />Chat Playground</Link>
      </nav>
    </header>
  );
}

export function SaveStateIndicator({ state }: { state: SaveState }) {
  if (state === "idle") return null;
  if (state === "saving") return <span className="saveStateIndicator tone-neutral"><Loader2 size={13} aria-hidden="true" className="spinIcon" />Saving...</span>;
  if (state === "saved") return <span className="saveStateIndicator tone-success"><CheckCircle2 size={13} aria-hidden="true" />All changes saved</span>;
  if (state === "error") return <span className="saveStateIndicator tone-danger"><PenSquare size={13} aria-hidden="true" />Save failed</span>;
  return <span className="saveStateIndicator tone-warning"><PenSquare size={13} aria-hidden="true" />Unsaved changes</span>;
}
