import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import { SettingsSummaryCards } from "./settings-summary-cards";

describe("SettingsSummaryCards", () => {
  it("renders all five summary cards from existing data only", () => {
    render(<SettingsSummaryCards data={{ workspaceStatus: "active", language: "en", planKey: "pilot", environment: "staging", memberCount: 8 }} />);

    const grid = screen.getByLabelText("Workspace summary");
    expect(within(grid).getByText("Workspace status")).toBeTruthy();
    expect(within(grid).getByText("active")).toBeTruthy();
    expect(within(grid).getByText("Language")).toBeTruthy();
    expect(within(grid).getByText("en")).toBeTruthy();
    expect(within(grid).getByText("Organisation plan")).toBeTruthy();
    expect(within(grid).getByText("pilot")).toBeTruthy();
    expect(within(grid).getByText("Environment")).toBeTruthy();
    expect(within(grid).getByText("staging")).toBeTruthy();
    expect(within(grid).getByText("Members")).toBeTruthy();
    expect(within(grid).getByText("8")).toBeTruthy();
  });
});
