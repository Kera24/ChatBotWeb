export type DevelopmentRole = "super_admin" | "org_owner" | "client_admin" | "contributor" | "viewer";

export type DevelopmentDashboardSession = {
  organisationId: string;
  workspaceId: string;
  userEmail: string;
  role: DevelopmentRole;
};

export type DevelopmentTenantConfigResult =
  | { configured: true; session: DevelopmentDashboardSession }
  | { configured: false; missing: string[] };

const DEFAULT_DEVELOPMENT_EMAIL = "dev-super-admin@example.test";
const DEFAULT_DEVELOPMENT_ROLE: DevelopmentRole = "super_admin";

export function getDevelopmentDashboardSession(): DevelopmentTenantConfigResult {
  const organisationId = process.env.NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID;
  const workspaceId = process.env.NEXT_PUBLIC_DEVELOPMENT_WORKSPACE_ID;
  const userEmail = process.env.NEXT_PUBLIC_DEVELOPMENT_USER_EMAIL ?? DEFAULT_DEVELOPMENT_EMAIL;
  const role = (process.env.NEXT_PUBLIC_DEVELOPMENT_ROLE ?? DEFAULT_DEVELOPMENT_ROLE) as DevelopmentRole;

  const requiredValues: Array<[string, string | undefined]> = [
    ["NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID", organisationId],
    ["NEXT_PUBLIC_DEVELOPMENT_WORKSPACE_ID", workspaceId],
  ];
  const missing = requiredValues
    .filter(([, value]) => !value)
    .map(([name]) => name);

  if (missing.length > 0) {
    return { configured: false, missing };
  }

  return {
    configured: true,
    session: {
      organisationId: organisationId as string,
      workspaceId: workspaceId as string,
      userEmail,
      role,
    },
  };
}

export function developmentDashboardHeaders(session: DevelopmentDashboardSession): HeadersInit {
  return {
    "X-Development-User-Email": session.userEmail,
    "X-Development-Role": session.role,
  };
}
