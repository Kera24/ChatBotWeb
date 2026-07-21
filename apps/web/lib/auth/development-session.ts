export type DevelopmentRole = "super_admin" | "org_owner" | "client_admin" | "contributor" | "viewer";

export type DevelopmentDashboardSession = {
  organisationId: string;
  workspaceId: string;
  userEmail: string;
  role: DevelopmentRole;
};

export type DevelopmentTenantConfigResult =
  | { configured: true; session: DevelopmentDashboardSession }
  | { configured: false; missing: string[]; invalid: string[] };

const DEVELOPMENT_ROLES: DevelopmentRole[] = [
  "super_admin",
  "org_owner",
  "client_admin",
  "contributor",
  "viewer",
];

export function getDevelopmentDashboardSession(): DevelopmentTenantConfigResult {
  const organisationId = process.env.NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID;
  const workspaceId = process.env.NEXT_PUBLIC_DEVELOPMENT_WORKSPACE_ID;
  const userEmail = process.env.NEXT_PUBLIC_DEVELOPMENT_USER_EMAIL;
  const role = process.env.NEXT_PUBLIC_DEVELOPMENT_ROLE;

  const requiredValues: Array<[string, string | undefined]> = [
    ["NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID", organisationId],
    ["NEXT_PUBLIC_DEVELOPMENT_WORKSPACE_ID", workspaceId],
    ["NEXT_PUBLIC_DEVELOPMENT_USER_EMAIL", userEmail],
    ["NEXT_PUBLIC_DEVELOPMENT_ROLE", role],
  ];
  const missing = requiredValues
    .filter(([, value]) => !value)
    .map(([name]) => name);
  const invalid = role && !isDevelopmentRole(role) ? ["NEXT_PUBLIC_DEVELOPMENT_ROLE"] : [];

  if (missing.length > 0 || invalid.length > 0) {
    return { configured: false, missing, invalid };
  }

  return {
    configured: true,
    session: {
      organisationId: organisationId as string,
      workspaceId: workspaceId as string,
      userEmail: userEmail as string,
      role: role as DevelopmentRole,
    },
  };
}

export function developmentDashboardHeaders(session: DevelopmentDashboardSession): HeadersInit {
  return {
    "X-Development-User-Email": session.userEmail,
    "X-Development-Role": session.role,
  };
}

function isDevelopmentRole(value: string): value is DevelopmentRole {
  return DEVELOPMENT_ROLES.includes(value as DevelopmentRole);
}
