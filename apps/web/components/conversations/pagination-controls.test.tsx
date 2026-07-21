import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { PaginationControls } from "./pagination-controls";

describe("PaginationControls", () => {
  it("renders labelled previous and next links with serialized query state", () => {
    render(<PaginationControls basePath="/conversations" status="active" channel="api" limit={10} offset={20} hasNext />);

    expect(screen.getByRole("navigation", { name: "Conversation pages" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Previous" }).getAttribute("href")).toBe(
      "/conversations?status=active&channel=api&limit=10&offset=10",
    );
    expect(screen.getByRole("link", { name: "Next" }).getAttribute("href")).toBe(
      "/conversations?status=active&channel=api&limit=10&offset=30",
    );
  });

  it("marks unavailable pagination actions as disabled for assistive tech", () => {
    render(<PaginationControls basePath="/conversations" limit={20} offset={0} hasNext={false} />);

    expect(screen.getByRole("link", { name: "Previous" }).getAttribute("aria-disabled")).toBe("true");
    expect(screen.getByRole("link", { name: "Next" }).getAttribute("aria-disabled")).toBe("true");
  });
});
