import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { UsersHeader } from "./users-header";

describe("UsersHeader", () => {
  it("renders member count, role summary, and quick links", () => {
    render(<UsersHeader organisationName="Yoranix College" workspaceName="Admissions Assistant" total={6} roleSummary="2 admins · 3 contributors · 1 viewer" inactiveCount={0} />);

    expect(screen.getByRole("heading", { name: "Users" })).toBeTruthy();
    expect(screen.getByText("6 members")).toBeTruthy();
    expect(screen.getByText("2 admins · 3 contributors · 1 viewer")).toBeTruthy();
    expect(screen.getByText("All members active")).toBeTruthy();

    const nav = screen.getByRole("navigation", { name: "Workspace quick links" });
    expect(nav.querySelector("a[href='/settings']")).toBeTruthy();
    expect(nav.querySelector("a[href='/dashboard']")).toBeTruthy();
  });

  it("shows a pending-review nudge when members are inactive", () => {
    render(<UsersHeader organisationName="Yoranix College" workspaceName="Admissions Assistant" total={6} roleSummary="" inactiveCount={2} />);
    expect(screen.getByText("2 inactive, may need review")).toBeTruthy();
  });
});
