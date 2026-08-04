import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { ZeroAssistantState } from "./overview-empty-states";

describe("ZeroAssistantState", () => {
  it("guides a new account toward creating its first assistant", () => {
    render(<ZeroAssistantState />);
    expect(screen.getByRole("heading", { name: "Create your first assistant" })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Create assistant/ }).getAttribute("href")).toBe("/assistants/new");
  });

  it("announces itself as a status region for screen readers", () => {
    render(<ZeroAssistantState />);
    expect(screen.getByRole("status")).toBeTruthy();
  });
});
