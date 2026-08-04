import { describe, expect, it, vi } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import { SaveBar } from "./save-bar";

function renderSaveBar(overrides: Partial<Parameters<typeof SaveBar>[0]> = {}) {
  const props = {
    dirty: false,
    saving: false,
    canManage: true,
    validationError: null,
    notice: null,
    error: null,
    isConflict: false,
    onSave: vi.fn(),
    onReset: vi.fn(),
    ...overrides,
  };
  render(<SaveBar {...props} />);
  return props;
}

describe("SaveBar", () => {
  it("renders nothing for users who cannot manage the workspace", () => {
    const { container } = render(<SaveBar dirty saving={false} canManage={false} validationError={null} notice={null} error={null} isConflict={false} onSave={vi.fn()} onReset={vi.fn()} />);
    expect(container.textContent).toBe("");
  });

  it("shows an up-to-date status and disables actions when clean", () => {
    renderSaveBar({ dirty: false });
    expect(screen.getByText("Up to date")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Save changes/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Reset/ })).toBeDisabled();
  });

  it("shows an unsaved-changes indicator and enables actions when dirty", () => {
    renderSaveBar({ dirty: true });
    expect(screen.getByText("Unsaved changes")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Save changes/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Reset/ })).toBeEnabled();
  });

  it("shows a saving state and disables actions while in flight", () => {
    renderSaveBar({ dirty: true, saving: true });
    expect(screen.getByRole("button", { name: /Saving/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Reset/ })).toBeDisabled();
  });

  it("shows a validation error and disables save", () => {
    renderSaveBar({ dirty: true, validationError: "Workspace name is required." });
    expect(screen.getByRole("alert")).toHaveTextContent("Workspace name is required.");
    expect(screen.getByRole("button", { name: /Save changes/ })).toBeDisabled();
  });

  it("shows a conflict message distinctly from a generic error", () => {
    renderSaveBar({ dirty: true, error: "These settings changed in another request.", isConflict: true });
    expect(screen.getByText("These settings changed in another request.")).toBeTruthy();
  });

  it("shows a success notice", () => {
    renderSaveBar({ notice: "Workspace settings saved." });
    expect(screen.getByRole("status")).toHaveTextContent("Workspace settings saved.");
  });

  it("calls onSave and onReset", async () => {
    const user = userEvent.setup();
    const props = renderSaveBar({ dirty: true });

    await user.click(screen.getByRole("button", { name: /Save changes/ }));
    expect(props.onSave).toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /Reset/ }));
    expect(props.onReset).toHaveBeenCalled();
  });
});
