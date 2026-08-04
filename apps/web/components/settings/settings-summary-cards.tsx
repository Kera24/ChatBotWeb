export type SettingsSummaryData = {
  workspaceStatus: string;
  language: string;
  planKey: string;
  environment: string;
  memberCount: number;
};

export function SettingsSummaryCards({ data }: { data: SettingsSummaryData }) {
  const cards = [
    { key: "status", label: "Workspace status", value: data.workspaceStatus, detail: "Current workspace lifecycle status." },
    { key: "language", label: "Language", value: data.language, detail: "Default language for this workspace." },
    { key: "plan", label: "Organisation plan", value: data.planKey, detail: "Billing plan for this organisation." },
    { key: "environment", label: "Environment", value: data.environment, detail: "Deployment environment serving this workspace." },
    { key: "members", label: "Members", value: String(data.memberCount), detail: "Organisation memberships returned by the API." },
  ];

  return (
    <section className="settingsMetricGrid" aria-label="Workspace summary">
      {cards.map((card) => (
        <article className="settingsMetricCard" key={card.key}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
          <p>{card.detail}</p>
        </article>
      ))}
    </section>
  );
}
