import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "app/globals.css"), "utf8");
const finalLayer = css.slice(css.indexOf("/* Semantic contrast system: final readability layer */"));

const requiredTokens = [
  "--background",
  "--foreground",
  "--surface",
  "--surface-elevated",
  "--surface-muted",
  "--text-primary",
  "--text-secondary",
  "--text-muted",
  "--border",
  "--border-strong",
  "--primary",
  "--primary-foreground",
  "--danger",
  "--success",
  "--warning",
  "--focus-ring",
];

describe("global contrast theme", () => {
  it("defines the required semantic colour tokens around the Yoranix primary colour", () => {
    expect(finalLayer).toContain("--primary: #1b2a4a");
    for (const token of requiredTokens) expect(finalLayer).toContain(token);
  });

  it("keeps OS dark preference from making white cards inherit light text", () => {
    expect(finalLayer).toContain("@media (prefers-color-scheme: dark)");
    expect(finalLayer).toContain("--surface-elevated: #ffffff");
    expect(finalLayer).toContain("--text-primary: #071225");
  });

  it("forces light cards and state panels to readable dark foreground tokens", () => {
    expect(finalLayer).toMatch(/\.statePanel[\s\S]*color: var\(--text-primary\) !important/);
    expect(finalLayer).toMatch(/\.wizardPanel[\s\S]*background-color: var\(--surface-elevated\)/);
    expect(finalLayer).toMatch(/\.confirmDialog[\s\S]*color: var\(--text-primary\) !important/);
  });

  it("defines readable dark surface foregrounds without forcing all text white", () => {
    expect(finalLayer).toContain("--dark-text-primary: #ffffff");
    expect(finalLayer).toContain("--dark-text-secondary: #dbe4f0");
    expect(finalLayer).toMatch(/:is\(\.sidebar, \.assistantWizardRail, \.authPreview/);
    expect(finalLayer).not.toContain("body * {\n  color: #ffffff");
  });

  it("sets explicit form, placeholder, disabled, autofill, and focus contrast", () => {
    expect(finalLayer).toMatch(/:is\(input, textarea, select\)[\s\S]*color: var\(--text-primary\) !important/);
    expect(finalLayer).toMatch(/:is\(input, textarea\)::placeholder[\s\S]*color: #6b778a !important/);
    expect(finalLayer).toMatch(/-webkit-text-fill-color: var\(--text-primary\) !important/);
    expect(finalLayer).toMatch(/:focus-visible[\s\S]*outline: 3px solid var\(--focus-ring\) !important/);
    expect(finalLayer).toMatch(/:disabled[\s\S]*color: #526070 !important/);
  });

  it("covers onboarding wizard readable states and publish surfaces", () => {
    for (const selector of [".wizardSteps li[data-state=\"active\"]", ".uploadDropzone", ".playgroundQuestion", ".embedCard pre", ".successPanel", ".publishErrors"]) {
      expect(finalLayer).toContain(selector);
    }
  });

  it("protects landing and dashboard shell theme boundaries", () => {
    expect(finalLayer).toContain(".landingPage :is(.featureCard");
    expect(finalLayer).toContain(".landingHero .landingButtonPrimary");
    expect(finalLayer).toContain(":is(.navLink, .wizardSteps li)");
  });
});