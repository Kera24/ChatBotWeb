import type { BillingSubscription } from "../../lib/api/billing";

function formatDate(value: string | null) {
  if (!value) return "Not set";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}

export function BillingMetrics({ subscription }: { subscription: BillingSubscription }) {
  const usageLabel =
    subscription.usage.assistants_limit === null
      ? `${subscription.usage.assistants_used} (unlimited)`
      : `${subscription.usage.assistants_used} / ${subscription.usage.assistants_limit}`;

  const cards = [
    { key: "plan", label: "Current plan", value: subscription.plan.name, detail: `${subscription.plan.price_display} ${subscription.plan.cadence}` },
    { key: "usage", label: "Assistants used", value: usageLabel, detail: "Active assistants counted against your plan limit." },
    { key: "period", label: "Current period ends", value: formatDate(subscription.current_period_end), detail: "When the next billing cycle begins." },
    { key: "renewal", label: subscription.cancel_at_period_end ? "Cancels on" : "Renews on", value: formatDate(subscription.current_period_end), detail: subscription.cancel_at_period_end ? "Access continues until this date." : "Your subscription renews automatically." },
  ];

  return (
    <section className="settingsMetricGrid" aria-label="Billing summary">
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
