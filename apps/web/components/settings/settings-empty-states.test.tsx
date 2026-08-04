import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { WorkspaceMissingState } from "./settings-empty-states";

describe("WorkspaceMissingState", () => {
  it("renders a workspace-missing state with a real navigation action", () => {
    render(<WorkspaceMissingState />);

    expect(screen.getByRole("heading", { name: "Workspace not found" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to My Assistants" }).getAttribute("href")).toBe("/dashboard");
  });
});
