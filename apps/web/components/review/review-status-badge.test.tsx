import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { ReviewStatusBadge } from "./review-status-badge";

describe("ReviewStatusBadge", () => {
  it("renders status text that is not dependent on colour", () => {
    render(<ReviewStatusBadge status="knowledge_gap" />);
    expect(screen.getByText("Knowledge gap")).toBeTruthy();
    expect(screen.getByLabelText("Review status: Knowledge gap")).toBeTruthy();
  });

  it.each([
    ["open", "Open"],
    ["reviewed", "Reviewed"],
    ["dismissed", "Dismissed"],
  ])("renders %s as accessible text", (status, label) => {
    render(<ReviewStatusBadge status={status} />);
    expect(screen.getByText(label)).toBeTruthy();
  });

  it("falls back to open when status is missing", () => {
    render(<ReviewStatusBadge status={null} />);
    expect(screen.getByText("Open")).toBeTruthy();
  });

  it("renders unknown statuses with a readable label", () => {
    render(<ReviewStatusBadge status="something_new" />);
    expect(screen.getByText("something new")).toBeTruthy();
  });
});
