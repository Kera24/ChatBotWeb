import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { ConversationStatusBadge } from "./conversation-status-badge";

describe("ConversationStatusBadge", () => {
  it("renders status text that is not dependent on colour", () => {
    render(<ConversationStatusBadge status="active" />);

    expect(screen.getByText("Active")).toBeTruthy();
  });

  it.each([
    ["fallback", "Fallback"],
    ["failed", "Failed"],
    ["low_confidence", "Low confidence"],
  ])("renders answer state %s as accessible text", (state, label) => {
    render(<ConversationStatusBadge status={state} answerState />);

    expect(screen.getByText(label)).toBeTruthy();
  });
});
