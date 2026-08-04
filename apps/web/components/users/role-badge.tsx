import { Crown, Eye, Pencil, Shield, ShieldCheck, type LucideIcon } from "lucide-react";

export const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super admin",
  org_owner: "Organisation owner",
  client_admin: "Client admin",
  contributor: "Contributor",
  viewer: "Viewer",
};

export const ROLE_DESCRIPTIONS: Record<string, string> = {
  super_admin: "Full administrative access across the platform.",
  org_owner: "Full control over this organisation, including members and all assistants.",
  client_admin: "Can manage members, assistants, and workspace configuration.",
  contributor: "Can create and edit assistants and knowledge, but cannot manage members.",
  viewer: "Read-only access to assistants, conversations, and analytics.",
};

export const ROLE_RANK: Record<string, number> = {
  super_admin: 4,
  org_owner: 3,
  client_admin: 2,
  contributor: 1,
  viewer: 0,
};

const ROLE_TONE: Record<string, string> = {
  super_admin: "admin",
  org_owner: "admin",
  client_admin: "admin",
  contributor: "info",
  viewer: "neutral",
};

const ROLE_ICON: Record<string, LucideIcon> = {
  super_admin: Crown,
  org_owner: ShieldCheck,
  client_admin: Shield,
  contributor: Pencil,
  viewer: Eye,
};

export function roleLabel(role: string) {
  return ROLE_LABELS[role] || role.replace(/_/g, " ");
}

export function roleDescription(role: string) {
  return ROLE_DESCRIPTIONS[role] || "Permissions for this role are not documented.";
}

export function roleRank(role: string) {
  return ROLE_RANK[role] ?? 0;
}

export function isRoleDowngrade(currentRole: string, nextRole: string) {
  return roleRank(nextRole) < roleRank(currentRole);
}

export function RoleBadge({ role }: { role: string }) {
  const tone = ROLE_TONE[role] ?? "neutral";
  const Icon = ROLE_ICON[role] ?? Shield;
  return (
    <span className={`roleBadge tone-${tone}`} aria-label={`Role: ${roleLabel(role)}`}>
      <Icon size={13} aria-hidden="true" />
      {roleLabel(role)}
    </span>
  );
}
