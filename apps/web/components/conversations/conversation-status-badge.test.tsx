import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { ConversationStatusBadge } from "./conversation-status-badge";

describe("ConversationStatusBadge", () => {
  it("renders status text that is not dependent on colour", () => {
    render(<ConversationStatusBadge status="active" />);

    expect(screen.getByText("Active")).toBeTruthy();
    expect(screen.getByLabelText("Status: Active")).toBeTruthy();
  });

  it.each([
    ["fallback", "Fallback"],
    ["failed", "Failed"],
    ["low_confidence", "Low confidence"],
  ])("renders answer state %s as accessible text", (state, label) => {
    render(<ConversationStatusBadge status={state} answerState />);

    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByLabelText(`Answer state: ${label}`)).toBeTruthy();
  });

  it("falls back to pending when status is missing", () => {
    render(<ConversationStatusBadge status={null} answerState />);
    expect(screen.getByText("Pending")).toBeTruthy();
  });

  it("renders unknown statuses with a readable label", () => {
    render(<ConversationStatusBadge status="something_new" />);
    expect(screen.getByText("something new")).toBeTruthy();
  });
});
