import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { PaginationControls } from "./pagination-controls";

describe("PaginationControls", () => {
  it("renders labelled previous and next links with serialized query state", () => {
    render(<PaginationControls basePath="/conversations" status="active" channel="api" limit={10} offset={20} hasNext assistantId="assistant-1" />);

    expect(screen.getByRole("navigation", { name: "Conversation pages" })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Previous/ }).getAttribute("href")).toBe(
      "/conversations?assistant=assistant-1&status=active&channel=api&limit=10&offset=10",
    );
    expect(screen.getByRole("link", { name: /Next/ }).getAttribute("href")).toBe(
      "/conversations?assistant=assistant-1&status=active&channel=api&limit=10&offset=30",
    );
    expect(screen.getByText("Showing 21–30")).toBeTruthy();
  });

  it("marks unavailable pagination actions as disabled for assistive tech and removes them from tab order", () => {
    render(<PaginationControls basePath="/conversations" limit={20} offset={0} hasNext={false} assistantId="assistant-1" />);

    const previous = screen.getByRole("link", { name: /Previous/ });
    const next = screen.getByRole("link", { name: /Next/ });
    expect(previous.getAttribute("aria-disabled")).toBe("true");
    expect(next.getAttribute("aria-disabled")).toBe("true");
    expect(previous.getAttribute("tabindex")).toBe("-1");
    expect(next.getAttribute("tabindex")).toBe("-1");
  });
});
