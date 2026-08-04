import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { SettingsHeader } from "./settings-header";

describe("SettingsHeader", () => {
  it("renders workspace identity, organisation context, and environment badge", () => {
    render(<SettingsHeader workspaceName="Admissions Workspace" organisationName="Yoranix College" planKey="pilot" environment="staging" saveState="idle" />);

    expect(screen.getByRole("heading", { name: "Workspace Settings" })).toBeTruthy();
    expect(screen.getByText(/Admissions Workspace/)).toBeTruthy();
    expect(screen.getByText("staging environment")).toBeTruthy();
    expect(screen.getByText("Yoranix College · pilot plan")).toBeTruthy();
  });

  it("renders quick links to members, widget builder, and chat playground", () => {
    render(<SettingsHeader workspaceName="Admissions Workspace" organisationName="Yoranix College" planKey="pilot" environment="staging" saveState="idle" />);

    const nav = screen.getByRole("navigation", { name: "Workspace quick links" });
    expect(nav.querySelector("a[href='/users']")).toBeTruthy();
    expect(nav.querySelector("a[href='/widgets']")).toBeTruthy();
    expect(nav.querySelector("a[href='/chatbot']")).toBeTruthy();
  });

  it("shows no save-state indicator when idle", () => {
    render(<SettingsHeader workspaceName="Admissions Workspace" organisationName="Yoranix College" planKey="pilot" environment="staging" saveState="idle" />);
    expect(screen.queryByText(/Unsaved changes|Saving|All changes saved|Save failed/)).not.toBeInTheDocument();
  });

  it.each([
    ["dirty", "Unsaved changes"],
    ["saving", "Saving..."],
    ["saved", "All changes saved"],
    ["error", "Save failed"],
  ] as const)("shows the %s save state", (state, label) => {
    render(<SettingsHeader workspaceName="Admissions Workspace" organisationName="Yoranix College" planKey="pilot" environment="staging" saveState={state} />);
    expect(screen.getByText(label)).toBeTruthy();
  });
});
