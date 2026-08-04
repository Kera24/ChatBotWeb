import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import type { MembershipRecord } from "../../lib/api/users";
import { ConfirmActionDialog } from "./role-dialog";

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

describe("ConfirmActionDialog", () => {
  it("renders nothing when there is no pending action", () => {
    const { container } = render(<ConfirmActionDialog action={null} pending={false} onCancel={vi.fn()} onConfirm={vi.fn()} />);
    expect(container.textContent).toBe("");
  });

  it("explains a role downgrade before confirming", () => {
    render(<ConfirmActionDialog action={{ type: "role", membership: buildMember(), role: "viewer" }} pending={false} onCancel={vi.fn()} onConfirm={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Change role?" })).toBeTruthy();
    expect(screen.getByText(/Client admin to Viewer/)).toBeTruthy();
    expect(screen.getByText(/reduces their access/)).toBeTruthy();
  });

  it("explains a deactivation before confirming", () => {
    render(<ConfirmActionDialog action={{ type: "status", membership: buildMember(), status: "inactive" }} pending={false} onCancel={vi.fn()} onConfirm={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: "Deactivate membership?" })).toBeTruthy();
    expect(screen.getByText(/ada@example.test will be set to inactive/)).toBeTruthy();
  });

  it("calls onConfirm and onCancel", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmActionDialog action={{ type: "status", membership: buildMember(), status: "inactive" }} pending={false} onCancel={onCancel} onConfirm={onConfirm} />);

    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("disables actions while pending", () => {
    render(<ConfirmActionDialog action={{ type: "status", membership: buildMember(), status: "inactive" }} pending onCancel={vi.fn()} onConfirm={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Saving" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Cancel" }).hasAttribute("disabled")).toBe(true);
  });
});
