export type DashboardRole = "super_admin" | "org_owner" | "client_admin" | "contributor" | "viewer";

export type DashboardSession = {
  organisationId: string;
  workspaceId: string;
  userEmail: string;
  fullName: string | null;
  role: DashboardRole;
  onboardingComplete: boolean;
  organisationName: string;
  workspaceName: string;
};

export type DevelopmentRole = DashboardRole;
export type DevelopmentDashboardSession = DashboardSession;

export type AuthContext = {
  user: {
    id: string;
    email: string;
    full_name: string | null;
    status: string;
    email_verified: boolean;
    onboarding_complete: boolean;
  };
  organisation: { name: string; slug: string; plan_key: string; status: string };
  workspace: { name: string; slug: string; status: string };
  membership: { role: DashboardRole; status: string };
  organisation_id: string;
  workspace_id: string;
  role: DashboardRole;
  onboarding_complete: boolean;
};

export type DevelopmentTenantConfigResult =
  | { configured: true; session: DashboardSession }
  | { configured: false; missing: string[]; invalid: string[] };

export function dashboardSessionFromAuthContext(context: AuthContext): DashboardSession {
  return {
    organisationId: context.organisation_id,
    workspaceId: context.workspace_id,
    userEmail: context.user.email,
    fullName: context.user.full_name,
    role: context.role,
    onboardingComplete: context.onboarding_complete,
    organisationName: context.organisation.name,
    workspaceName: context.workspace.name,
  };
}

export function developmentDashboardHeaders(_session?: DashboardSession): HeadersInit {
  void _session;
  return {};
}

export function getDevelopmentDashboardSession(): DevelopmentTenantConfigResult {
  return { configured: false, missing: [], invalid: [] };
}
