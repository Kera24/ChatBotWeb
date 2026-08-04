import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { ReviewPaginationControls } from "./review-pagination-controls";

describe("ReviewPaginationControls", () => {
  it("renders labelled previous and next links with serialized query state and a real total", () => {
    render(
      <ReviewPaginationControls
        basePath="/review/unanswered"
        answerState="failed"
        reviewStatus="knowledge_gap"
        channel="api"
        limit={10}
        offset={10}
        total={45}
        hasNext
        assistantId="assistant-1"
      />,
    );

    expect(screen.getByRole("navigation", { name: "Review queue pages" })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Next/ }).getAttribute("href")).toBe(
      "/review/unanswered?assistant=assistant-1&answer_state=failed&review_status=knowledge_gap&channel=api&limit=10&offset=20",
    );
    expect(screen.getByText("Showing 11–20 of 45")).toBeTruthy();
  });

  it("marks unavailable pagination actions as disabled and removes them from tab order", () => {
    render(<ReviewPaginationControls basePath="/review/unanswered" limit={20} offset={0} total={0} hasNext={false} assistantId="assistant-1" />);

    const previous = screen.getByRole("link", { name: /Previous/ });
    const next = screen.getByRole("link", { name: /Next/ });
    expect(previous.getAttribute("aria-disabled")).toBe("true");
    expect(next.getAttribute("aria-disabled")).toBe("true");
    expect(previous.getAttribute("tabindex")).toBe("-1");
    expect(screen.getByText("No results")).toBeTruthy();
  });
});
