import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen, userEvent, waitFor, within } from "../../test/test-utils";
import * as usersApi from "../../lib/api/users";
import type { MembershipListMeta, MembershipRecord } from "../../lib/api/users";
import type { DevelopmentDashboardSession } from "../../lib/auth/development-session";
import { UsersManagementClient } from "./users-management-client";

vi.mock("../../lib/api/users");

const session: DevelopmentDashboardSession = {
  organisationId: "org-1",
  workspaceId: "workspace-1",
  userEmail: "admin@example.test",
  fullName: "Admin User",
  role: "client_admin",
  onboardingComplete: true,
  organisationName: "Yoranix College",
  workspaceName: "Admissions Assistant",
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
  membership({
    id: "membership-2",
    user: { id: "user-2", email: "viewer@example.test", full_name: "Viewer User", status: "active", created_at: "2026-07-03T00:00:00.000Z", updated_at: "2026-07-03T00:00:00.000Z" },
    role: "viewer",
    created_at: "2026-07-03T00:00:00.000Z",
    updated_at: "2026-07-03T00:00:00.000Z",
  }),
  membership({
    id: "membership-3",
    user: { id: "user-3", email: "inactive@example.test", full_name: "Inactive User", status: "active", created_at: "2026-07-04T00:00:00.000Z", updated_at: "2026-07-04T00:00:00.000Z" },
    role: "contributor",
    status: "inactive",
    created_at: "2026-07-04T00:00:00.000Z",
    updated_at: "2026-07-04T00:00:00.000Z",
  }),
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
  it("renders the header, metrics, and unsupported invitation guidance", () => {
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    expect(screen.getByRole("heading", { name: "Users" })).toBeInTheDocument();
    expect(screen.getByText("Total members")).toBeInTheDocument();
    expect(screen.getByText("Admins")).toBeInTheDocument();
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

  it("sorts members by joined date", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.selectOptions(screen.getByLabelText("Sort"), "joined-desc");
    const rows = screen.getAllByRole("listitem");
    expect(within(rows[0]).getByText("inactive@example.test")).toBeTruthy();
  });

  it("opens the member detail drawer for a selected member", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.click(screen.getByRole("button", { name: /Viewer User/ }));

    const drawer = screen.getByRole("dialog", { name: /Viewer User/ });
    expect(within(drawer).getByText("Admissions Assistant")).toBeInTheDocument();
  });

  it("applies a role upgrade immediately without a confirmation dialog", async () => {
    const user = userEvent.setup();
    vi.mocked(usersApi.updateMembershipRole).mockResolvedValue(envelope({ ...memberships[1], role: "org_owner" }));
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.click(screen.getByRole("button", { name: /Viewer User/ }));
    await user.selectOptions(screen.getByLabelText("Role for viewer@example.test"), "org_owner");

    expect(screen.queryByRole("dialog", { name: "Change role?" })).not.toBeInTheDocument();
    await waitFor(() => expect(usersApi.updateMembershipRole).toHaveBeenCalledWith(session, "membership-2", "org_owner"));
    expect(await screen.findByText("viewer@example.test role updated.")).toBeInTheDocument();
  });

  it("requires confirmation before a role downgrade", async () => {
    const user = userEvent.setup();
    vi.mocked(usersApi.updateMembershipRole).mockResolvedValue(envelope({ ...memberships[2], role: "viewer" }));
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.click(screen.getByRole("button", { name: /Inactive User/ }));
    await user.selectOptions(screen.getByLabelText("Role for inactive@example.test"), "viewer");

    expect(usersApi.updateMembershipRole).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog", { name: "Change role?" });
    expect(within(dialog).getByText(/reduces their access/)).toBeTruthy();

    await user.click(within(dialog).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(usersApi.updateMembershipRole).toHaveBeenCalledWith(session, "membership-3", "viewer"));
  });

  it("confirms destructive membership deactivation", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.click(screen.getByRole("button", { name: /Viewer User/ }));
    await user.click(screen.getByRole("button", { name: "Deactivate" }));
    const dialog = screen.getByRole("dialog", { name: "Deactivate membership?" });
    await user.click(within(dialog).getByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(usersApi.updateMembershipStatus).toHaveBeenCalledWith(session, "membership-2", "inactive"));
  });

  it("protects the current user's own membership from self-service changes", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.click(screen.getByRole("button", { name: /Admin User/ }));
    const drawer = screen.getByRole("dialog", { name: /Admin User/ });
    expect(within(drawer).getByText("You")).toBeTruthy();
    expect(within(drawer).queryByLabelText("Role for admin@example.test")).not.toBeInTheDocument();
    expect(within(drawer).queryByRole("button", { name: "Deactivate" })).not.toBeInTheDocument();
  });

  it("renders read-only controls for viewers", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={viewerSession} initialMemberships={memberships} meta={meta} />);

    expect(screen.getByText("Your role can view memberships but cannot change roles or access.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Viewer User/ }));
    expect(screen.queryByLabelText("Role for viewer@example.test")).not.toBeInTheDocument();
  });

  it("shows refresh errors and an empty state when there are no members", async () => {
    const user = userEvent.setup();
    vi.mocked(usersApi.listMemberships).mockRejectedValue(new Error("network"));
    render(<UsersManagementClient session={session} initialMemberships={[]} meta={meta} />);

    expect(screen.getByRole("heading", { name: "No members yet" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Refresh" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Members could not be refreshed.");
  });

  it("shows a distinct empty state and clear action when filters match nothing", async () => {
    const user = userEvent.setup();
    render(<UsersManagementClient session={session} initialMemberships={memberships} meta={meta} />);

    await user.type(screen.getByLabelText("Search"), "no-such-member");
    expect(screen.getByRole("heading", { name: "No matching members" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear all filters" }));
    expect(screen.getByText("viewer@example.test")).toBeInTheDocument();
  });
});
