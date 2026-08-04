"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useState } from "react";

import { listMemberships, updateMembershipRole, updateMembershipStatus, type MembershipListMeta, type MembershipRecord } from "../../lib/api/users";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { MemberDetailDrawer } from "./member-detail-drawer";
import { MemberDirectory } from "./member-directory";
import { MemberFilters, type MemberSortOption } from "./member-filters";
import { ConfirmActionDialog, type PendingMemberAction } from "./role-dialog";
import { isRoleDowngrade, roleRank } from "./role-badge";
import { computeUsersMetrics, UsersMetrics } from "./users-metrics";
import { NoMembersState, NoResultsState, ReadOnlyNotice } from "./users-empty-states";
import { UsersHeader } from "./users-header";

type UsersManagementClientProps = {
  session: DevelopmentDashboardSession;
  initialMemberships: MembershipRecord[];
  meta: MembershipListMeta;
};

export function UsersManagementClient({ session, initialMemberships, meta }: UsersManagementClientProps) {
  const reduceMotion = useReducedMotion();
  const [memberships, setMemberships] = useState(initialMemberships);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sort, setSort] = useState<MemberSortOption>("name-asc");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<PendingMemberAction>(null);
  const canManage = session.role === "org_owner" || session.role === "client_admin" || session.role === "super_admin";

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const matches = memberships.filter((membership) => {
      const matchesSearch = !q || [membership.user.email, membership.user.full_name, membership.organisation_name, membership.workspace_name].some((value) => value?.toLowerCase().includes(q));
      const matchesRole = !roleFilter || membership.role === roleFilter;
      const matchesStatus = !statusFilter || membership.status === statusFilter;
      return matchesSearch && matchesRole && matchesStatus;
    });
    return sortMemberships(matches, sort);
  }, [memberships, roleFilter, search, sort, statusFilter]);

  const selected = memberships.find((membership) => membership.id === selectedId) ?? null;
  const metrics = computeUsersMetrics(memberships);
  const roleSummary = `${metrics.admins} admin${metrics.admins === 1 ? "" : "s"} · ${metrics.contributors} contributor${metrics.contributors === 1 ? "" : "s"} · ${metrics.viewers} viewer${metrics.viewers === 1 ? "" : "s"}`;

  function clearFilters() {
    setSearch("");
    setRoleFilter("");
    setStatusFilter("");
  }

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

  function requestRoleChange(membership: MembershipRecord, role: string) {
    if (role === membership.role) return;
    if (isRoleDowngrade(membership.role, role)) {
      setConfirmAction({ type: "role", membership, role });
      return;
    }
    void performRoleChange(membership, role);
  }

  function requestStatusChange(membership: MembershipRecord, status: string) {
    setConfirmAction({ type: "status", membership, status });
  }

  async function performRoleChange(membership: MembershipRecord, role: string) {
    setPendingId(membership.id);
    setError(null);
    try {
      const response = await updateMembershipRole(session, membership.id, role);
      setMemberships((current) => current.map((item) => (item.id === membership.id ? response.data : item)));
      setNotice(`${response.data.user.email} role updated.`);
    } catch {
      setError("Role update was rejected by the membership API.");
    } finally {
      setPendingId(null);
    }
  }

  async function performStatusChange(membership: MembershipRecord, status: string) {
    setPendingId(membership.id);
    setError(null);
    try {
      const response = await updateMembershipStatus(session, membership.id, status);
      setMemberships((current) => current.map((item) => (item.id === membership.id ? response.data : item)));
      setNotice(`${response.data.user.email} membership ${response.data.status}.`);
    } catch {
      setError("Membership status change was rejected by the membership API.");
    } finally {
      setPendingId(null);
    }
  }

  async function confirmPendingAction() {
    if (!confirmAction) return;
    if (confirmAction.type === "role") await performRoleChange(confirmAction.membership, confirmAction.role);
    else await performStatusChange(confirmAction.membership, confirmAction.status);
    setConfirmAction(null);
  }

  const pageMotion = reduceMotion ? { initial: false, animate: {} } : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } };

  return (
    <motion.section className="usersPage premiumUsersPage" aria-labelledby="users-title" {...pageMotion}>
      <UsersHeader
        organisationName={session.organisationName}
        workspaceName={session.workspaceName}
        total={metrics.total}
        roleSummary={roleSummary}
        inactiveCount={metrics.inactive}
      />

      <UsersMetrics data={metrics} />

      <MemberFilters
        search={search}
        onSearchChange={setSearch}
        roleFilter={roleFilter}
        onRoleFilterChange={setRoleFilter}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        sort={sort}
        onSortChange={setSort}
        roles={meta.roles}
        statuses={meta.statuses}
        onRefresh={() => void refresh()}
      />

      <section className="usersNotice" aria-label="Supported user management operations">
        <strong>Supported contract</strong>
        <p>This dashboard manages existing organisation memberships only. Invitation, last-login, and separate workspace-membership contracts are not present in the backend and are intentionally omitted.</p>
      </section>

      {!canManage ? <ReadOnlyNotice /> : null}
      {notice ? <div className="widgetNotice" role="status">{notice}</div> : null}
      {error ? <div className="statePanel urgentState" role="alert"><h2>User action failed</h2><p>{error}</p></div> : null}

      <div className="usersPanelHeader">
        <div><p className="sectionKicker">Members</p><h3>Organisation access</h3></div>
        <span>{filtered.length} shown</span>
      </div>

      {memberships.length === 0 ? (
        <NoMembersState />
      ) : filtered.length === 0 ? (
        <NoResultsState onClear={clearFilters} />
      ) : (
        <MemberDirectory members={filtered} selectedId={selectedId} currentUserEmail={session.userEmail} onSelect={setSelectedId} />
      )}

      <MemberDetailDrawer
        member={selected}
        canManage={canManage}
        isCurrentUser={Boolean(selected && selected.user.email.toLowerCase() === session.userEmail.toLowerCase())}
        roles={meta.roles}
        pending={pendingId === selected?.id}
        onClose={() => setSelectedId(null)}
        onRequestRoleChange={requestRoleChange}
        onRequestStatusChange={requestStatusChange}
      />

      <ConfirmActionDialog
        action={confirmAction}
        pending={pendingId === confirmAction?.membership.id}
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => void confirmPendingAction()}
      />
    </motion.section>
  );
}

function sortMemberships(list: MembershipRecord[], sort: MemberSortOption) {
  const copy = [...list];
  switch (sort) {
    case "name-asc":
      copy.sort((a, b) => (a.user.full_name || a.user.email).localeCompare(b.user.full_name || b.user.email));
      break;
    case "role-desc":
      copy.sort((a, b) => roleRank(b.role) - roleRank(a.role));
      break;
    case "status-asc":
      copy.sort((a, b) => a.status.localeCompare(b.status));
      break;
    case "joined-desc":
      copy.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      break;
    case "joined-asc":
      copy.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
      break;
  }
  return copy;
}
