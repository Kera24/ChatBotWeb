import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { MemberStatusBadge } from "./member-status-badge";

describe("MemberStatusBadge", () => {
  it("renders active status with accessible text", () => {
    render(<MemberStatusBadge status="active" />);
    expect(screen.getByText("active")).toBeTruthy();
    expect(screen.getByLabelText("Status: active")).toBeTruthy();
  });

  it("renders inactive status with accessible text", () => {
    render(<MemberStatusBadge status="inactive" />);
    expect(screen.getByText("inactive")).toBeTruthy();
  });

  it("renders unknown statuses without crashing", () => {
    render(<MemberStatusBadge status="pending_invite" />);
    expect(screen.getByText("pending invite")).toBeTruthy();
  });
});
