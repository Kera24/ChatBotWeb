import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent, within } from "../../test/test-utils";
import { PlanPicker } from "./plan-picker";

describe("PlanPicker", () => {
  it("marks the organisation's current plan and offers upgrades for higher tiers", () => {
    render(<PlanPicker currentPlanKey="starter" pendingPlanKey={null} canManage onSelectPlan={vi.fn()} />);

    const starterCard = screen.getByRole("heading", { name: "Starter" }).closest(".pricingCard") as HTMLElement;
    expect(within(starterCard).getAllByText("Current plan")).toHaveLength(2); // badge + disabled button
    expect(within(starterCard).getByRole("button")).toBeDisabled();

    const professionalCard = screen.getByRole("heading", { name: "Professional" }).closest(".pricingCard") as HTMLElement;
    expect(within(professionalCard).getByRole("button", { name: "Upgrade" })).toBeTruthy();
  });

  it("offers a downgrade action for lower tiers than the current plan", () => {
    render(<PlanPicker currentPlanKey="professional" pendingPlanKey={null} canManage onSelectPlan={vi.fn()} />);
    const starterCard = screen.getByRole("heading", { name: "Starter" }).closest(".pricingCard") as HTMLElement;
    expect(within(starterCard).getByRole("button", { name: "Downgrade" })).toBeTruthy();
  });

  it("calls onSelectPlan with the chosen plan key", async () => {
    const onSelectPlan = vi.fn();
    const user = userEvent.setup();
    render(<PlanPicker currentPlanKey="starter" pendingPlanKey={null} canManage onSelectPlan={onSelectPlan} />);

    const professionalCard = screen.getByRole("heading", { name: "Professional" }).closest(".pricingCard") as HTMLElement;
    await user.click(within(professionalCard).getByRole("button", { name: "Upgrade" }));

    expect(onSelectPlan).toHaveBeenCalledWith("professional");
  });

  it("shows a redirecting state for the plan currently being checked out", () => {
    render(<PlanPicker currentPlanKey="starter" pendingPlanKey="professional" canManage onSelectPlan={vi.fn()} />);
    const professionalCard = screen.getByRole("heading", { name: "Professional" }).closest(".pricingCard") as HTMLElement;
    expect(within(professionalCard).getByRole("button")).toBeDisabled();
    expect(within(professionalCard).getByText(/Redirecting to checkout/)).toBeTruthy();
  });

  it("disables plan changes and explains why when the viewer cannot manage billing", () => {
    render(<PlanPicker currentPlanKey="starter" pendingPlanKey={null} canManage={false} onSelectPlan={vi.fn()} />);
    const professionalCard = screen.getByRole("heading", { name: "Professional" }).closest(".pricingCard") as HTMLElement;
    expect(within(professionalCard).getByRole("button")).toBeDisabled();
    expect(screen.getByText(/Only organisation owners can change the subscription plan/)).toBeTruthy();
  });
});
