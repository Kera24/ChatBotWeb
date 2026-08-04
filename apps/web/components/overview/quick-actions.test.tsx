import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { QuickActions } from "./quick-actions";

describe("QuickActions", () => {
  it("always shows workspace-level actions even with no assistant selected", () => {
    render(<QuickActions primaryAssistantId={null} />);
    expect(screen.getByRole("link", { name: /Create assistant/ }).getAttribute("href")).toBe("/assistants/new");
    expect(screen.getByRole("link", { name: /Manage team/ }).getAttribute("href")).toBe("/users");
    expect(screen.getByRole("link", { name: /Open settings/ }).getAttribute("href")).toBe("/settings");
  });

  it("does not show assistant-specific actions when no assistant can be resolved", () => {
    render(<QuickActions primaryAssistantId={null} />);
    expect(screen.queryByRole("link", { name: /Upload knowledge/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Test assistant/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Configure widget/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Review conversations/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Resolve knowledge gaps/ })).not.toBeInTheDocument();
  });

  it("scopes assistant-specific actions to the resolved assistant when one exists", () => {
    render(<QuickActions primaryAssistantId="assistant-1" />);
    expect(screen.getByRole("link", { name: /Upload knowledge/ }).getAttribute("href")).toBe("/knowledge?assistant=assistant-1");
    expect(screen.getByRole("link", { name: /Resolve knowledge gaps/ }).getAttribute("href")).toBe("/review/unanswered?assistant=assistant-1");
  });
});
