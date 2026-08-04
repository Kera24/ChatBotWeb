export type UsersMetricsData = {
  total: number;
  active: number;
  inactive: number;
  admins: number;
  contributors: number;
  viewers: number;
};

export function computeUsersMetrics(memberships: Array<{ role: string; status: string }>): UsersMetricsData {
  return {
    total: memberships.length,
    active: memberships.filter((membership) => membership.status === "active").length,
    inactive: memberships.filter((membership) => membership.status !== "active").length,
    admins: memberships.filter((membership) => ["org_owner", "client_admin", "super_admin"].includes(membership.role)).length,
    contributors: memberships.filter((membership) => membership.role === "contributor").length,
    viewers: memberships.filter((membership) => membership.role === "viewer").length,
  };
}

export function UsersMetrics({ data }: { data: UsersMetricsData }) {
  const cards = [
    { key: "total", label: "Total members", value: data.total, detail: "Organisation memberships returned by the API." },
    { key: "active", label: "Active", value: data.active, detail: "Memberships allowed through RBAC checks." },
    { key: "inactive", label: "Inactive", value: data.inactive, detail: "Memberships currently blocked from access." },
    { key: "admins", label: "Admins", value: data.admins, detail: "Organisation owners and client admins." },
    { key: "contributors", label: "Contributors", value: data.contributors, detail: "Can create and edit content." },
    { key: "viewers", label: "Viewers", value: data.viewers, detail: "Read-only workspace access." },
  ];

  return (
    <section className="usersMetricGrid" aria-label="Membership metrics">
      {cards.map((card) => (
        <article className="usersMetricCard" key={card.key}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
          <p>{card.detail}</p>
        </article>
      ))}
    </section>
  );
}
