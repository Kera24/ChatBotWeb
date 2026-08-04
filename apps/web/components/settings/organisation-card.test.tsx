import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { OrganisationCard } from "./organisation-card";

const organisation = {
  id: "org-1",
  name: "Yoranix College",
  slug: "yoranix-college",
  status: "active",
  plan_key: "pilot",
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
};

const membershipSummary = { total: 8, active: 7, inactive: 1, administrators: 2 };

describe("OrganisationCard", () => {
  it("renders read-only organisation info, membership breakdown, and a link to manage access", () => {
    render(<OrganisationCard organisation={organisation} membershipSummary={membershipSummary} />);

    expect(screen.getByText("Yoranix College")).toBeTruthy();
    expect(screen.getByText("yoranix-college")).toBeTruthy();
    expect(screen.getByText("pilot")).toBeTruthy();
    expect(screen.getByText("8")).toBeTruthy();
    expect(screen.getByText("7")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Manage access" }).getAttribute("href")).toBe("/users");
  });

  it("renders no input elements since this section is display-only", () => {
    render(<OrganisationCard organisation={organisation} membershipSummary={membershipSummary} />);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
