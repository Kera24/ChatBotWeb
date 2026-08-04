import { describe, expect, it } from "vitest";

import { render, screen, within } from "../../test/test-utils";
import { computeUsersMetrics, UsersMetrics } from "./users-metrics";

describe("computeUsersMetrics", () => {
  it("derives totals purely from existing role and status fields", () => {
    const metrics = computeUsersMetrics([
      { role: "org_owner", status: "active" },
      { role: "client_admin", status: "active" },
      { role: "contributor", status: "inactive" },
      { role: "viewer", status: "active" },
      { role: "viewer", status: "active" },
    ]);

    expect(metrics.total).toBe(5);
    expect(metrics.active).toBe(4);
    expect(metrics.inactive).toBe(1);
    expect(metrics.admins).toBe(2);
    expect(metrics.contributors).toBe(1);
    expect(metrics.viewers).toBe(2);
  });
});

describe("UsersMetrics", () => {
  it("renders all six summary cards", () => {
    render(<UsersMetrics data={{ total: 5, active: 4, inactive: 1, admins: 2, contributors: 1, viewers: 2 }} />);

    const grid = screen.getByLabelText("Membership metrics");
    for (const label of ["Total members", "Active", "Inactive", "Admins", "Contributors", "Viewers"]) {
      expect(within(grid).getByText(label)).toBeTruthy();
    }
  });
});
