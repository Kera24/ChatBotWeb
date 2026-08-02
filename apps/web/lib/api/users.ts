import { dashboardApiGet, dashboardApiPatch } from "./client";
import type { DevelopmentDashboardSession } from "../auth/development-session";

export type MembershipUser = {
  id: string;
  email: string;
  full_name: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type MembershipRecord = {
  id: string;
  organisation_id: string;
  organisation_name: string;
  organisation_slug: string;
  workspace_id: string;
  workspace_name: string;
  workspace_slug: string;
  user: MembershipUser;
  role: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type MembershipListMeta = {
  count: number;
  roles: string[];
  statuses: string[];
};

function workspacePath(session: DevelopmentDashboardSession, suffix: string) {
  return `/api/v1/workspaces/${session.workspaceId}${suffix}`;
}

function tenantParams(session: DevelopmentDashboardSession) {
  return { organisation_id: session.organisationId };
}

export function listMemberships(session: DevelopmentDashboardSession) {
  return dashboardApiGet<MembershipRecord[], MembershipListMeta>({
    path: workspacePath(session, "/memberships"),
    session,
    searchParams: tenantParams(session),
  });
}

export function updateMembershipRole(session: DevelopmentDashboardSession, membershipId: string, role: string) {
  return dashboardApiPatch<MembershipRecord>({
    path: workspacePath(session, `/memberships/${membershipId}/role`),
    session,
    searchParams: tenantParams(session),
    body: { role },
  });
}

export function updateMembershipStatus(session: DevelopmentDashboardSession, membershipId: string, status: string) {
  return dashboardApiPatch<MembershipRecord>({
    path: workspacePath(session, `/memberships/${membershipId}/status`),
    session,
    searchParams: tenantParams(session),
    body: { status },
  });
}
