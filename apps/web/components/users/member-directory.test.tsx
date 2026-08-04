import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import type { MembershipRecord } from "../../lib/api/users";
import { MemberDirectory } from "./member-directory";

function buildMember(overrides: Partial<MembershipRecord> = {}): MembershipRecord {
  return {
    id: "membership-1",
    organisation_id: "org-1",
    organisation_name: "Yoranix College",
    organisation_slug: "yoranix-college",
    workspace_id: "workspace-1",
    workspace_name: "Admissions Assistant",
    workspace_slug: "admissions",
    user: {
      id: "user-1",
      email: "ada@example.test",
      full_name: "Ada Lovelace",
      status: "active",
      created_at: "2026-07-01T00:00:00.000Z",
      updated_at: "2026-07-02T00:00:00.000Z",
    },
    role: "client_admin",
    status: "active",
    created_at: "2026-07-01T00:00:00.000Z",
    updated_at: "2026-07-02T00:00:00.000Z",
    ...overrides,
  };
}

describe("MemberDirectory", () => {
  it("renders each member as an accessible list item with role, status, and workspace", () => {
    render(<MemberDirectory members={[buildMember()]} selectedId={null} currentUserEmail="viewer@example.test" onSelect={vi.fn()} />);

    expect(screen.getByRole("list", { name: "Workspace members" })).toBeTruthy();
    expect(screen.getByText("Ada Lovelace")).toBeTruthy();
    expect(screen.getByText("ada@example.test")).toBeTruthy();
    expect(screen.getByText("Client admin")).toBeTruthy();
    expect(screen.getByText("active")).toBeTruthy();
    expect(screen.getByText("Admissions Assistant")).toBeTruthy();
  });

  it("marks the current user's row with a badge", () => {
    render(<MemberDirectory members={[buildMember()]} selectedId={null} currentUserEmail="ADA@example.test" onSelect={vi.fn()} />);
    expect(screen.getByText("You")).toBeTruthy();
  });

  it("does not show the current-user badge for other members", () => {
    render(<MemberDirectory members={[buildMember()]} selectedId={null} currentUserEmail="someone-else@example.test" onSelect={vi.fn()} />);
    expect(screen.queryByText("You")).not.toBeInTheDocument();
  });

  it("calls onSelect with the membership id when a row is activated", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<MemberDirectory members={[buildMember()]} selectedId={null} currentUserEmail="x@example.test" onSelect={onSelect} />);

    await user.click(screen.getByRole("button", { name: /Ada Lovelace/ }));
    expect(onSelect).toHaveBeenCalledWith("membership-1");
  });

  it("marks the selected row as pressed", () => {
    render(<MemberDirectory members={[buildMember()]} selectedId="membership-1" currentUserEmail="x@example.test" onSelect={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Ada Lovelace/ }).getAttribute("aria-pressed")).toBe("true");
  });
});
