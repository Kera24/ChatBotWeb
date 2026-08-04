import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import type { MembershipRecord } from "../../lib/api/users";
import { MemberDetailDrawer } from "./member-detail-drawer";

function buildMember(overrides: Partial<MembershipRecord> = {}): MembershipRecord {
  return {
    id: "membership-1",
    organisation_id: "org-1",
    organisation_name: "Yoranix College",
    organisation_slug: "yoranix-college",
    workspace_id: "workspace-1",
    workspace_name: "Admissions Assistant",
    workspace_slug: "admissions",
    user: { id: "user-1", email: "ada@example.test", full_name: "Ada Lovelace", status: "active", created_at: "2026-07-01T00:00:00.000Z", updated_at: "2026-07-02T00:00:00.000Z" },
    role: "client_admin",
    status: "active",
    created_at: "2026-07-01T00:00:00.000Z",
    updated_at: "2026-07-02T00:00:00.000Z",
    ...overrides,
  };
}

const roles = ["org_owner", "client_admin", "contributor", "viewer"];

describe("MemberDetailDrawer", () => {
  it("renders nothing when no member is selected", () => {
    const { container } = render(<MemberDetailDrawer member={null} canManage roles={roles} pending={false} isCurrentUser={false} onClose={vi.fn()} onRequestRoleChange={vi.fn()} onRequestStatusChange={vi.fn()} />);
    expect(container.textContent).toBe("");
  });

  it("shows identity, role, status, organisation, workspace, and a permission summary", () => {
    render(<MemberDetailDrawer member={buildMember()} canManage roles={roles} pending={false} isCurrentUser={false} onClose={vi.fn()} onRequestRoleChange={vi.fn()} onRequestStatusChange={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: /Ada Lovelace/ })).toBeTruthy();
    expect(screen.getByText("ada@example.test")).toBeTruthy();
    expect(screen.getByText("Yoranix College")).toBeTruthy();
    expect(screen.getByText("Admissions Assistant")).toBeTruthy();
    expect(screen.getByRole("heading", { name: /What Client admin can do/ })).toBeTruthy();
  });

  it("lets a manager request a role change", async () => {
    const user = userEvent.setup();
    const onRequestRoleChange = vi.fn();
    render(<MemberDetailDrawer member={buildMember()} canManage roles={roles} pending={false} isCurrentUser={false} onClose={vi.fn()} onRequestRoleChange={onRequestRoleChange} onRequestStatusChange={vi.fn()} />);

    await user.selectOptions(screen.getByLabelText("Role for ada@example.test"), "viewer");
    expect(onRequestRoleChange).toHaveBeenCalledWith(expect.objectContaining({ id: "membership-1" }), "viewer");
  });

  it("lets a manager request deactivation", async () => {
    const user = userEvent.setup();
    const onRequestStatusChange = vi.fn();
    render(<MemberDetailDrawer member={buildMember()} canManage roles={roles} pending={false} isCurrentUser={false} onClose={vi.fn()} onRequestRoleChange={vi.fn()} onRequestStatusChange={onRequestStatusChange} />);

    await user.click(screen.getByRole("button", { name: "Deactivate" }));
    expect(onRequestStatusChange).toHaveBeenCalledWith(expect.objectContaining({ id: "membership-1" }), "inactive");
  });

  it("protects the current user from self-managing role or status", () => {
    render(<MemberDetailDrawer member={buildMember()} canManage roles={roles} pending={false} isCurrentUser onClose={vi.fn()} onRequestRoleChange={vi.fn()} onRequestStatusChange={vi.fn()} />);

    expect(screen.queryByLabelText("Role for ada@example.test")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deactivate" })).not.toBeInTheDocument();
    expect(screen.getByText(/cannot change your own role or deactivate your own membership/)).toBeTruthy();
  });

  it("hides management controls entirely for viewers", () => {
    render(<MemberDetailDrawer member={buildMember()} canManage={false} roles={roles} pending={false} isCurrentUser={false} onClose={vi.fn()} onRequestRoleChange={vi.fn()} onRequestStatusChange={vi.fn()} />);
    expect(screen.queryByLabelText("Role for ada@example.test")).not.toBeInTheDocument();
    expect(screen.getByText("Your role can view memberships but cannot change access.")).toBeTruthy();
  });

  it("closes when the close button is activated", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<MemberDetailDrawer member={buildMember()} canManage roles={roles} pending={false} isCurrentUser={false} onClose={onClose} onRequestRoleChange={vi.fn()} onRequestStatusChange={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Close member details" }));
    expect(onClose).toHaveBeenCalled();
  });
});
