import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import { MemberFilters } from "./member-filters";

function renderFilters(overrides: Partial<Parameters<typeof MemberFilters>[0]> = {}) {
  const props = {
    search: "",
    onSearchChange: vi.fn(),
    roleFilter: "",
    onRoleFilterChange: vi.fn(),
    statusFilter: "",
    onStatusFilterChange: vi.fn(),
    sort: "name-asc" as const,
    onSortChange: vi.fn(),
    roles: ["org_owner", "client_admin", "contributor", "viewer"],
    statuses: ["active", "inactive"],
    onRefresh: vi.fn(),
    ...overrides,
  };
  render(<MemberFilters {...props} />);
  return props;
}

describe("MemberFilters", () => {
  it("renders labelled search, role, status, and sort controls", () => {
    renderFilters();
    expect(screen.getByLabelText("Search")).toBeTruthy();
    expect(screen.getByLabelText("Role")).toBeTruthy();
    expect(screen.getByLabelText("Status")).toBeTruthy();
    expect(screen.getByLabelText("Sort")).toBeTruthy();
  });

  it("calls onSearchChange as the user types", async () => {
    const user = userEvent.setup();
    const props = renderFilters();
    await user.type(screen.getByLabelText("Search"), "a");
    expect(props.onSearchChange).toHaveBeenCalled();
  });

  it("shows active filter chips with individual clear buttons", () => {
    renderFilters({ search: "ada", roleFilter: "viewer", statusFilter: "active" });
    expect(screen.getByLabelText("Active member filters")).toBeTruthy();
    expect(screen.getByText("Search: ada")).toBeTruthy();
    expect(screen.getByText("Role: Viewer")).toBeTruthy();
    expect(screen.getByText("Status: active")).toBeTruthy();
  });

  it("clears an individual filter via its chip", async () => {
    const user = userEvent.setup();
    const props = renderFilters({ roleFilter: "viewer" });
    await user.click(screen.getByRole("button", { name: "Remove filter: Role: Viewer" }));
    expect(props.onRoleFilterChange).toHaveBeenCalledWith("");
  });

  it("disables clear-all when no filters are active and enables it otherwise", async () => {
    const user = userEvent.setup();
    const props = renderFilters({ search: "ada" });
    const clearAll = screen.getByRole("button", { name: "Clear all" });
    expect(clearAll.hasAttribute("disabled")).toBe(false);
    await user.click(clearAll);
    expect(props.onSearchChange).toHaveBeenCalledWith("");
  });

  it("calls onRefresh when refresh is clicked", async () => {
    const user = userEvent.setup();
    const props = renderFilters();
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(props.onRefresh).toHaveBeenCalled();
  });
});
