import { Layers, Settings, Users as UsersIcon } from "lucide-react";
import Link from "next/link";

export function UsersHeader({
  organisationName,
  workspaceName,
  total,
  roleSummary,
  inactiveCount,
}: {
  organisationName: string;
  workspaceName: string;
  total: number;
  roleSummary: string;
  inactiveCount: number;
}) {
  return (
    <header className="premiumUsersHero">
      <div className="usersHeroMain">
        <div>
          <p className="eyebrow">Workspace members</p>
          <h2 id="users-title">Users</h2>
          <p>Manage {organisationName}&rsquo;s access to {workspaceName} using existing organisation roles and membership status.</p>
          <div className="usersHeroMeta" aria-label="Membership summary">
            <span><UsersIcon size={14} aria-hidden="true" />{total} member{total === 1 ? "" : "s"}</span>
            <span>{roleSummary}</span>
            {inactiveCount > 0 ? <span className="usersHeroPending">{inactiveCount} inactive, may need review</span> : <span>All members active</span>}
          </div>
        </div>
      </div>
      <nav className="usersQuickLinks" aria-label="Workspace quick links">
        <Link href="/settings"><Settings size={15} aria-hidden="true" />Workspace settings</Link>
        <Link href="/dashboard"><Layers size={15} aria-hidden="true" />My Assistants</Link>
      </nav>
    </header>
  );
}
