import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { isRoleDowngrade, roleDescription, roleLabel, roleRank, RoleBadge } from "./role-badge";

describe("RoleBadge", () => {
  it("renders a readable label and accessible name", () => {
    render(<RoleBadge role="org_owner" />);
    expect(screen.getByText("Organisation owner")).toBeTruthy();
    expect(screen.getByLabelText("Role: Organisation owner")).toBeTruthy();
  });

  it("renders unknown roles with a readable fallback label", () => {
    render(<RoleBadge role="future_role" />);
    expect(screen.getByText("future role")).toBeTruthy();
  });
});

describe("roleLabel / roleDescription", () => {
  it("maps every known role to a human label and non-empty description", () => {
    for (const role of ["super_admin", "org_owner", "client_admin", "contributor", "viewer"]) {
      expect(roleLabel(role)).not.toBe(role);
      expect(roleDescription(role).length).toBeGreaterThan(0);
    }
  });
});

describe("roleRank / isRoleDowngrade", () => {
  it("ranks roles from viewer (lowest) to super_admin (highest)", () => {
    expect(roleRank("viewer")).toBeLessThan(roleRank("contributor"));
    expect(roleRank("contributor")).toBeLessThan(roleRank("client_admin"));
    expect(roleRank("client_admin")).toBeLessThan(roleRank("org_owner"));
    expect(roleRank("org_owner")).toBeLessThan(roleRank("super_admin"));
  });

  it("detects downgrades correctly", () => {
    expect(isRoleDowngrade("client_admin", "viewer")).toBe(true);
    expect(isRoleDowngrade("viewer", "client_admin")).toBe(false);
    expect(isRoleDowngrade("contributor", "contributor")).toBe(false);
  });
});
