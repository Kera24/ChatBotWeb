import { PlaceholderPage } from "../../components/placeholder-page";

export default function UsersPage() {
  return (
    <PlaceholderPage
      eyebrow="Users"
      title="Access shaped around responsibility"
      description="A placeholder for future users, roles, invitations, workspace access, and least-privilege permission management."
      primaryMetric="RBAC"
      primaryMetricLabel="planned for tenancy sprint"
      focusItems={[
        "Organisation and workspace membership",
        "Role-based access controls",
        "Audit-aware administrative actions",
      ]}
    />
  );
}
