import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UsersManagementClient, UsersSkeleton } from "./users-management-client";
import * as usersApi from "../../lib/api/users";
import type { MembershipListMeta, MembershipRecord } from "../../lib/api/users";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";

vi.mock("../../lib/api/users");

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  role: "client_admin",
};

const viewerSession: DevelopmentDashboardSession = { ...session, role: "viewer", userEmail: "viewer@example.test" };

const meta: MembershipListMeta = {
  count: 3,
  roles: ["client_admin", "contributor", "org_owner", "viewer"],
  statuses: ["active", "inactive"],
};

function membership(overrides: Partial<MembershipRecord> = {}): MembershipRecord {
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
      email: "admin@example.test",
      full_name: "Admin User",
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

const memberships = [
  membership(),
  membership({ id: "membership-2", user: { id: "user-2", email: "viewer@example.test", full_name: "Viewer User", status: "active", created_at: "2026-07-03T00:00:00.000Z", updated_at: "2026-07-03T00:00:00.000Z" }, role: "viewer" }),
  membership({ id: "membership-3", user: { id: "user-3", email: "inactive@example.test", full_name: "Inactive User", status: "active", created_at: "2026-07-04T00:00:00.000Z", updated_at: "2026-07-04T00:00:00.000Z" }, role: "contributor", status: "inactive" }),
];

function envelope<T>(data: T) {
  return { success: true, data, meta: {} };
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(usersApi.listMemberships).mockResolvedValue({ success: true, data: memberships, meta });
  vi.mocked(usersApi.updateMembershipRole).mockResolvedValue(envelope({ ...memberships[1], role: "contributor" }));
  vi.mocked(usersApi.updateMembershipStatus).mockResolvedValue(envelope({ ...memberships[1], status: "inactive" }));
});

describe("UsersManagementClient", () => {
  it("renders metrics, rows, and unsupported invitation guidance", () => {
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    expect(screen.getByRole("heading", { name: "Users and role management" })).toBeInTheDocument();
    expect(screen.getByText("Total members")).toBeInTheDocument();
    expect(screen.getByText("Administrators")).toBeInTheDocument();
    expect(screen.getByText(/Invitation, last-login, and separate workspace-membership contracts are not present/)).toBeInTheDocument();
    expect(screen.getByText("viewer@example.test")).toBeInTheDocument();
  });

  it("filters by search, role, and status", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.type(screen.getByLabelText("Search"), "inactive");
    expect(screen.getByText("inactive@example.test")).toBeInTheDocument();
    expect(screen.queryByText("viewer@example.test")).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText("Search"));
    await user.selectOptions(screen.getByLabelText("Role"), "viewer");
    expect(screen.getByText("viewer@example.test")).toBeInTheDocument();
    expect(screen.queryByText("inactive@example.test")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Role"), "");
    await user.selectOptions(screen.getByLabelText("Status"), "inactive");
    expect(screen.getByText("inactive@example.test")).toBeInTheDocument();
    expect(screen.queryByText("viewer@example.test")).not.toBeInTheDocument();
  });

  it("opens details for a selected member", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.click(screen.getByRole("button", { name: "Viewer User" }));

    const details = screen.getByRole("heading", { name: "Member profile" }).closest("section");
    expect(details).not.toBeNull();
    expect(within(details as HTMLElement).getByText("Viewer User")).toBeInTheDocument();
    expect(within(details as HTMLElement).getByText("Admissions Assistant")).toBeInTheDocument();
  });

  it("updates a role through the API", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.selectOptions(screen.getByLabelText("Role for viewer@example.test"), "contributor");

    await waitFor(() => expect(usersApi.updateMembershipRole).toHaveBeenCalledWith(session, "membership-2", "contributor"));
    expect(await screen.findByText("viewer@example.test role updated.")).toBeInTheDocument();
  });

  it("confirms destructive membership deactivation", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.click(screen.getByRole("button", { name: "Viewer User" }));
    await user.click(screen.getByRole("button", { name: "Deactivate" }));
    const dialog = screen.getByRole("dialog", { name: "Deactivate membership?" });
    await user.click(within(dialog).getByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(usersApi.updateMembershipStatus).toHaveBeenCalledWith(session, "membership-2", "inactive"));
  });

  it("renders read-only controls for viewers", () => {
    render(<UsersManagementClient session={viewerSession} initialMemberships={memberships} meta={meta} />);

    expect(screen.queryByLabelText("Role for viewer@example.test")).not.toBeInTheDocument();
    expect(screen.getByText("Your role can view memberships but cannot change access.")).toBeInTheDocument();
  });

  it("shows refresh errors and empty state", async () => {
    const user = userEvent.setup();
    vi.mocked(usersApi.listMemberships).mockRejectedValue(new Error("network"));
    render(<UsersManagementClient session={session} initialMemberships={[]} meta={meta} />);

    expect(screen.getByText("No matching members")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Refresh" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Members could not be refreshed.");
  });

  it("renders the loading skeleton", () => {
    render(<UsersSkeleton />);

    expect(screen.getByRole("heading", { name: "Loading Yoranix users" })).toBeInTheDocument();
  });
});

