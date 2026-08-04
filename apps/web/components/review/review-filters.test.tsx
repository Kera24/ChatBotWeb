import { describe, expect, it } from "vitest";

import { render, screen, userEvent } from "../../test/test-utils";
import { ReviewFilters } from "./review-filters";

describe("ReviewFilters", () => {
  it("renders labelled filter controls with expected state", async () => {
    const user = userEvent.setup();
    render(<ReviewFilters answerState="fallback" reviewStatus="open" channel="dashboard_test" limit={20} assistantId="assistant-1" />);

    const answerState = screen.getByLabelText("Answer state") as HTMLSelectElement;
    const reviewStatus = screen.getByLabelText("Review status") as HTMLSelectElement;
    await user.selectOptions(answerState, "failed");
    await user.selectOptions(reviewStatus, "knowledge_gap");

    expect(answerState.value).toBe("failed");
    expect(reviewStatus.value).toBe("knowledge_gap");
    expect(screen.getByRole("button", { name: "Apply review filters" })).toBeTruthy();
  });

  it("renders labelled date range controls", () => {
    render(<ReviewFilters limit={20} assistantId="assistant-1" createdAfter="2026-01-01" createdBefore="2026-02-01" />);
    expect((screen.getByLabelText("After") as HTMLInputElement).value).toBe("2026-01-01");
    expect((screen.getByLabelText("Before") as HTMLInputElement).value).toBe("2026-02-01");
  });

  it("preserves assistant context in the hidden field and clear-all link", () => {
    render(<ReviewFilters limit={20} assistantId="assistant-1" />);
    expect(screen.getByDisplayValue("assistant-1")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Clear all review filters" }).getAttribute("href")).toBe("/review/unanswered?assistant=assistant-1");
  });

  it("shows active filter chips with links that remove one filter at a time", () => {
    render(<ReviewFilters answerState="fallback" reviewStatus="open" channel="widget" limit={20} assistantId="assistant-1" />);

    expect(screen.getByLabelText("Active review filters")).toBeTruthy();
    expect(screen.getByText("Answer state: Fallback")).toBeTruthy();
    expect(screen.getByText("Review status: Open")).toBeTruthy();
    expect(screen.getByText("Channel: Widget")).toBeTruthy();

    const removeAnswerState = screen.getByRole("link", { name: "Remove filter: Answer state: Fallback" });
    const href = removeAnswerState.getAttribute("href") ?? "";
    expect(href).toContain("assistant=assistant-1");
    expect(href).toContain("review_status=open");
    expect(href).not.toContain("answer_state=");
  });

  it("shows a note when no filters are active", () => {
    render(<ReviewFilters limit={20} assistantId="assistant-1" />);
    expect(screen.getByText(/No filters applied/)).toBeTruthy();
    expect(screen.queryByLabelText("Active review filters")).toBeNull();
  });
});
