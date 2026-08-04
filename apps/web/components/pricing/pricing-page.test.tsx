import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import { PricingPage } from "./pricing-page";

describe("PricingPage", () => {
  it("renders every plan tier with its price and features", () => {
    render(<PricingPage />);

    expect(screen.getByRole("heading", { name: "Plans for every stage of AI adoption" })).toBeTruthy();
    for (const name of ["Starter", "Professional", "Enterprise"]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
    expect(screen.getByText("$0")).toBeTruthy();
    expect(screen.getByText("$249")).toBeTruthy();
    expect(screen.getByText("Custom")).toBeTruthy();
  });

  it("advertises the free trial without requiring a credit card", () => {
    render(<PricingPage />);
    expect(screen.getByText(/14-day free trial/i)).toBeTruthy();
    expect(screen.getByText(/no credit card required/i)).toBeTruthy();
  });

  it("routes the Starter and Professional plans to registration and Enterprise to a demo request", () => {
    render(<PricingPage />);

    const starterCard = screen.getByRole("heading", { name: "Starter" }).closest("div")?.parentElement as HTMLElement;
    expect(within(starterCard).getByRole("link", { name: /Start free trial/ }).getAttribute("href")).toBe("/register");

    const professionalCard = screen.getByRole("heading", { name: "Professional" }).closest("div")?.parentElement as HTMLElement;
    expect(within(professionalCard).getByRole("link", { name: /Start free trial/ }).getAttribute("href")).toBe("/register");

    const enterpriseCard = screen.getByRole("heading", { name: "Enterprise" }).closest("div")?.parentElement as HTMLElement;
    const demoLink = within(enterpriseCard).getByRole("link", { name: /Book a demo/ });
    expect(demoLink.getAttribute("href")).toMatch(/^mailto:/);
  });

  it("marks the Professional plan as the featured tier", () => {
    render(<PricingPage />);
    const professionalCard = screen.getByRole("heading", { name: "Professional" }).closest(".pricingCard");
    expect(professionalCard?.className).toContain("pricingFeatured");
  });

  it("provides navigation back to login and registration", () => {
    render(<PricingPage />);
    const nav = screen.getByRole("navigation", { name: "Pricing navigation" });
    expect(within(nav).getByRole("link", { name: "Log in" }).getAttribute("href")).toBe("/login");
    expect(within(nav).getByRole("link", { name: "Get Started" }).getAttribute("href")).toBe("/register");
  });
});
