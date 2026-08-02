"use client";

import { useMemo, useState } from "react";

import { listMemberships, updateMembershipRole, updateMembershipStatus, type MembershipListMeta, type MembershipRecord } from "../../lib/api/users";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

type UsersManagementClientProps = {
  session: DevelopmentDashboardSession;
  initialMemberships: MembershipRecord[];
  meta: MembershipListMeta;
};

type PendingAction =
  | { type: "status"; membership: MembershipRecord; status: string }
  | null;

const ROLE_LABELS: Record<string, string> = {
  org_owner: "Organisation owner",
  client_admin: "Client admin",
  contributor: "Contributor",
  viewer: "Viewer",
};

export function UsersManagementClient({ session, initialMemberships, meta }: UsersManagementClientProps) {
  const [memberships, setMemberships] = useState(initialMemberships);
  const [selectedId, setSelectedId] = useState(initialMemberships[0]?.id ?? null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<PendingAction>(null);
  const canManage = session.role === "org_owner" || session.role === "client_admin" || session.role === "super_admin";

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return memberships.filter((membership) => {
      const matchesSearch = !q || [membership.user.email, membership.user.full_name, membership.organisation_name, membership.workspace_name].some((value) => value?.toLowerCase().includes(q));
      const matchesRole = !roleFilter || membership.role === roleFilter;
      const matchesStatus = !statusFilter || membership.status === statusFilter;
      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [memberships, roleFilter, search, statusFilter]);

  const selected = memberships.find((membership) => membership.id === selectedId) ?? filtered[0] ?? null;
  const metrics = {
    total: memberships.length,
    active: memberships.filter((membership) => membership.status === "active").length,
    inactive: memberships.filter((membership) => membership.status !== "active").length,
    admins: memberships.filter((membership) => ["org_owner", "client_admin"].includes(membership.role)).length,
  };

  async function refresh() {
    setError(null);
    try {
      const response = await listMemberships(session);
      setMemberships(response.data);
      setNotice("Members refreshed.");
    } catch {
      setError("Members could not be refreshed.");
    }
  }

  async function changeRole(membership: MembershipRecord, role: string) {
    if (role === membership.role) return;
    setPendingId(membership.id);
    setError(null);
    try {
      const response = await updateMembershipRole(session, membership.id, role);
      setMemberships((current) => current.map((item) => item.id === membership.id ? response.data : item));
      setSelectedId(response.data.id);
      setNotice(`${response.data.user.email} role updated.`);
    } catch {
      setError("Role update was rejected by the membership API.");
    } finally {
      setPendingId(null);
    }
  }

  async function applyStatus() {
    if (!confirmAction) return;
    setPendingId(confirmAction.membership.id);
    setError(null);
    try {
      const response = await updateMembershipStatus(session, confirmAction.membership.id, confirmAction.status);
      setMemberships((current) => current.map((item) => item.id === confirmAction.membership.id ? response.data : item));
      setSelectedId(response.data.id);
      setNotice(`${response.data.user.email} membership ${response.data.status}.`);
      setConfirmAction(null);
    } catch {
      setError("Membership status change was rejected by the membership API.");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <section className="usersPage" aria-labelledby="users-title">
      <div className="usersHero">
        <div>
          <p className="eyebrow">Yuranix access control</p>
          <h2 id="users-title">Users and role management</h2>
          <p>Manage organisation memberships, role responsibility, and active access using the repository RBAC model.</p>
        </div>
        <div className="usersHeroAside">
          <strong>{metrics.total}</strong>
          <span>members in this organisation</span>
        </div>
      </div>

      <section className="usersMetricGrid" aria-label="Membership metrics">
        <Metric label="Total members" value={metrics.total} detail="Organisation memberships returned by the API." />
        <Metric label="Active" value={metrics.active} detail="Memberships allowed through RBAC checks." />
        <Metric label="Inactive" value={metrics.inactive} detail="Memberships currently blocked from organisation access." />
        <Metric label="Administrators" value={metrics.admins} detail="Organisation owners and client admins." />
      </section>

      <form className="usersFilters" aria-label="User filters">
        <label>Search<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, email, organisation, workspace" /></label>
        <label>Role<select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}><option value="">All roles</option>{meta.roles.map((role) => <option value={role} key={role}>{roleLabel(role)}</option>)}</select></label>
        <label>Status<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">All statuses</option>{meta.statuses.map((status) => <option value={status} key={status}>{status}</option>)}</select></label>
        <button className="smallButton" type="button" onClick={() => void refresh()}>Refresh</button>
      </form>

      <section className="usersNotice" aria-label="Supported user management operations">
        <strong>Supported contract</strong>
        <p>This dashboard manages existing organisation memberships only. Invitation, last-login, and separate workspace-membership contracts are not present in the backend and are intentionally omitted.</p>
      </section>

      {notice ? <div className="widgetNotice" role="status">{notice}</div> : null}
      {error ? <div className="statePanel urgentState" role="alert"><h2>User action failed</h2><p>{error}</p></div> : null}

      <div className="usersLayout">
        <section className="usersPanel" aria-labelledby="members-title">
          <div className="usersPanelHeader"><div><p className="sectionKicker">Members</p><h3 id="members-title">Organisation access</h3></div><span>{filtered.length} shown</span></div>
          {filtered.length === 0 ? <UsersEmpty title="No matching members" detail="Adjust search, role, or status filters." /> : (
            <div className="usersTableWrap">
              <table className="usersTable">
                <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead>
                <tbody>
                  {filtered.map((membership) => (
                    <tr className={selected?.id === membership.id ? "usersSelectedRow" : ""} key={membership.id}>
                      <td><button className="linkButton" type="button" onClick={() => setSelectedId(membership.id)}>{membership.user.full_name || "Unnamed user"}</button></td>
                      <td>{membership.user.email}</td>
                      <td>{canManage ? <RoleSelect membership={membership} roles={meta.roles} pending={pendingId === membership.id} onChange={changeRole} /> : roleLabel(membership.role)}</td>
                      <td><StatusBadge status={membership.status} /></td>
                      <td>{formatDate(membership.created_at)}</td>
                      <td><button className="smallButton" type="button" onClick={() => setSelectedId(membership.id)}>Details</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="usersPanel" aria-labelledby="member-detail-title">
          <div className="usersPanelHeader"><div><p className="sectionKicker">Details</p><h3 id="member-detail-title">Member profile</h3></div></div>
          {selected ? (
            <div className="usersDetailPanel">
              <h4>{selected.user.full_name || selected.user.email}</h4>
              <dl className="usersFacts">
                <div><dt>Email</dt><dd>{selected.user.email}</dd></div>
                <div><dt>User status</dt><dd>{selected.user.status}</dd></div>
                <div><dt>Membership status</dt><dd>{selected.status}</dd></div>
                <div><dt>Role</dt><dd>{roleLabel(selected.role)}</dd></div>
                <div><dt>Organisation</dt><dd>{selected.organisation_name}</dd></div>
                <div><dt>Workspace context</dt><dd>{selected.workspace_name}</dd></div>
                <div><dt>Created</dt><dd>{formatDate(selected.created_at)}</dd></div>
                <div><dt>Updated</dt><dd>{formatDate(selected.updated_at)}</dd></div>
              </dl>
              {canManage ? (
                <div className="usersActionBar">
                  {selected.status === "active" ? <button className="smallButton dangerButton" type="button" disabled={pendingId === selected.id} onClick={() => setConfirmAction({ type: "status", membership: selected, status: "inactive" })}>Deactivate</button> : <button className="smallButton" type="button" disabled={pendingId === selected.id} onClick={() => setConfirmAction({ type: "status", membership: selected, status: "active" })}>Reactivate</button>}
                </div>
              ) : <p className="mutedText">Your role can view memberships but cannot change access.</p>}
            </div>
          ) : <UsersEmpty title="No member selected" detail="Select a member row to inspect details." />}
        </section>
      </div>

      {confirmAction ? (
        <div className="dialogBackdrop" role="presentation">
          <section className="confirmDialog" role="dialog" aria-modal="true" aria-labelledby="membership-confirm-title">
            <h2 id="membership-confirm-title">{confirmAction.status === "active" ? "Reactivate membership?" : "Deactivate membership?"}</h2>
            <p>{confirmAction.membership.user.email} will be set to {confirmAction.status}. Server-side RBAC remains authoritative.</p>
            <div className="formActions"><button className="actionButton" type="button" onClick={() => setConfirmAction(null)}>Cancel</button><button className="actionButton" type="button" disabled={pendingId === confirmAction.membership.id} onClick={() => void applyStatus()}>Confirm</button></div>
          </section>
        </div>
      ) : null}
    </section>
  );
}

export function UsersSkeleton() {
  return <section className="usersPage" aria-busy="true" aria-live="polite"><div className="usersHero usersSkeletonBlock"><div><p className="eyebrow">Loading</p><h2>Loading Yuranix users</h2><p>Collecting tenant-scoped membership records.</p></div></div></section>;
}

function Metric({ label, value, detail }: { label: string; value: number; detail: string }) {
  return <article className="usersMetricCard"><span>{label}</span><strong>{value}</strong><p>{detail}</p></article>;
}

function RoleSelect({ membership, roles, pending, onChange }: { membership: MembershipRecord; roles: string[]; pending: boolean; onChange: (membership: MembershipRecord, role: string) => void }) {
  return <select aria-label={`Role for ${membership.user.email}`} value={membership.role} disabled={pending} onChange={(event) => void onChange(membership, event.target.value)}>{roles.map((role) => <option value={role} key={role}>{roleLabel(role)}</option>)}</select>;
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`usersStatusBadge users-status-${status}`}>{status}</span>;
}

function UsersEmpty({ title, detail }: { title: string; detail: string }) {
  return <div className="usersEmptyState"><h4>{title}</h4><p>{detail}</p></div>;
}

function roleLabel(role: string) {
  return ROLE_LABELS[role] || role.replace(/_/g, " ");
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}
