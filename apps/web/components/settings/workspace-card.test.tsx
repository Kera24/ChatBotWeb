import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import { WorkspaceCard } from "./workspace-card";

function renderCard(overrides: Partial<Parameters<typeof WorkspaceCard>[0]> = {}) {
  const props = {
    form: { name: "Admissions Workspace", default_language: "en" },
    slug: "admissions",
    updatedAt: "2026-07-02T00:00:00Z",
    canManage: true,
    dirty: false,
    saving: false,
    validationError: null,
    notice: null,
    error: null,
    isConflict: false,
    onFieldChange: vi.fn(),
    onSave: vi.fn(),
    onReset: vi.fn(),
    ...overrides,
  };
  render(<WorkspaceCard {...props} />);
  return props;
}

describe("WorkspaceCard", () => {
  it("renders editable fields, slug, and last-updated timestamp", () => {
    renderCard();
    expect(screen.getByDisplayValue("Admissions Workspace")).toBeTruthy();
    expect(screen.getByDisplayValue("en")).toBeTruthy();
    expect(screen.getByText("admissions")).toBeTruthy();
  });

  it("marks the panel as editable for managers", () => {
    renderCard({ canManage: true });
    expect(screen.getByText("Editable")).toBeTruthy();
  });

  it("marks the panel as read-only for non-managers and disables inputs", () => {
    renderCard({ canManage: false });
    expect(screen.getByText("Read-only")).toBeTruthy();
    expect(screen.getByLabelText("Workspace name")).toBeDisabled();
    expect(screen.getByLabelText("Default language")).toBeDisabled();
    expect(screen.getByText(/only organisation owners and client admins/i)).toBeTruthy();
  });

  it("calls onFieldChange as fields are edited", async () => {
    const user = userEvent.setup();
    const props = renderCard();
    await user.type(screen.getByLabelText("Workspace name"), "!");
    expect(props.onFieldChange).toHaveBeenCalled();
  });

  it("renders a validation error inline via the save bar", () => {
    renderCard({ dirty: true, validationError: "Workspace name is required." });
    expect(screen.getByRole("alert")).toHaveTextContent("Workspace name is required.");
  });
});
