import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import { NoMembersState, NoMemberSelectedState, NoResultsState, ReadOnlyNotice } from "./users-empty-states";

describe("users empty states", () => {
  it("shows a no-members state", () => {
    render(<NoMembersState />);
    expect(screen.getByRole("heading", { name: "No members yet" })).toBeTruthy();
  });

  it("shows a no-results state with a working clear action", async () => {
    const user = userEvent.setup();
    const onClear = vi.fn();
    render(<NoResultsState onClear={onClear} />);

    expect(screen.getByRole("heading", { name: "No matching members" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Clear all filters" }));
    expect(onClear).toHaveBeenCalled();
  });

  it("shows a no-member-selected state", () => {
    render(<NoMemberSelectedState />);
    expect(screen.getByRole("heading", { name: "No member selected" })).toBeTruthy();
  });

  it("shows a read-only notice", () => {
    render(<ReadOnlyNotice />);
    expect(screen.getByRole("status")).toHaveTextContent(/cannot change roles or access/i);
  });
});
