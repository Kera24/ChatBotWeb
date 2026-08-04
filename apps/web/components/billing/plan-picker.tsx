import { Check } from "lucide-react";

import type { PlanKey } from "../../lib/api/billing";

export type PlanOption = {
  key: PlanKey;
  name: string;
  priceDisplay: string;
  cadence: string;
  features: string[];
  featured?: true;
};

export const PLAN_OPTIONS: PlanOption[] = [
  { key: "starter", name: "Starter", priceDisplay: "$0", cadence: "to validate your first assistant", features: ["1 assistant", "Knowledge uploads", "Chatbot testing", "Basic analytics"] },
  { key: "professional", name: "Professional", priceDisplay: "$249", cadence: "per month", features: ["Up to 10 assistants", "Conversation review", "Advanced analytics", "Team access controls"], featured: true },
  { key: "enterprise", name: "Enterprise", priceDisplay: "Custom", cadence: "for governed organisations", features: ["Unlimited assistants", "Security review", "Priority support", "Workspace governance"] },
];

const PLAN_ORDER: PlanKey[] = ["starter", "professional", "enterprise"];

export function PlanPicker({
  currentPlanKey,
  pendingPlanKey,
  canManage,
  onSelectPlan,
}: {
  currentPlanKey: string;
  pendingPlanKey: string | null;
  canManage: boolean;
  onSelectPlan: (planKey: PlanKey) => void;
}) {
  const currentIndex = PLAN_ORDER.indexOf(currentPlanKey as PlanKey);

  return (
    <section className="settingsPanel" aria-labelledby="plan-picker-title">
      <div className="settingsPanelHeader">
        <div>
          <p className="sectionKicker">Subscription plans</p>
          <h3 id="plan-picker-title">Upgrade or downgrade your plan</h3>
        </div>
      </div>
      <div className="pricingGrid" role="list" aria-label="Available plans">
        {PLAN_OPTIONS.map((option) => {
          const isCurrent = option.key === currentPlanKey;
          const optionIndex = PLAN_ORDER.indexOf(option.key);
          const actionLabel = isCurrent ? "Current plan" : optionIndex > currentIndex ? "Upgrade" : "Downgrade";
          const isPending = pendingPlanKey === option.key;
          return (
            <article className={`pricingCard${option.featured ? " pricingFeatured" : ""}${isCurrent ? " planPickerCurrent" : ""}`} role="listitem" key={option.key}>
              {isCurrent ? <span className="environmentBadge tone-info">Current plan</span> : null}
              <h4>{option.name}</h4>
              <div className="priceLine">
                <strong>{option.priceDisplay}</strong>
                <span>{option.cadence}</span>
              </div>
              <ul>
                {option.features.map((feature) => (
                  <li key={feature}>
                    <Check size={14} aria-hidden="true" /> {feature}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className={option.featured && !isCurrent ? "actionButton" : "smallButton"}
                disabled={!canManage || isCurrent || isPending}
                onClick={() => onSelectPlan(option.key)}
              >
                {isPending ? "Redirecting to checkout..." : actionLabel}
              </button>
            </article>
          );
        })}
      </div>
      {!canManage ? <p className="reviewFilterNote">Only organisation owners can change the subscription plan.</p> : null}
    </section>
  );
}
