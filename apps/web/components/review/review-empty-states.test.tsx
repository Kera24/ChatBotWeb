import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import { NoAssistantSelectedState, NoReviewItemsState, NoFilterResultsState, ReviewItemNotFoundState } from "./review-empty-states";

describe("review empty states", () => {
  it("prompts the user to select an assistant", () => {
    render(<NoAssistantSelectedState />);
    expect(screen.getByRole("heading", { name: "No assistant selected" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to My Assistants" }).getAttribute("href")).toBe("/dashboard");
  });

  it("shows a no-items state with real navigation actions, not generic conversation copy", () => {
    render(<NoReviewItemsState assistantId="assistant-1" />);
    expect(screen.getByRole("heading", { name: "No flagged answers yet" })).toBeTruthy();
    expect(screen.queryByText(/conversations have been recorded/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Chat Playground" }).getAttribute("href")).toBe("/chatbot?assistant=assistant-1");
    expect(screen.getByRole("link", { name: "Add knowledge" }).getAttribute("href")).toBe("/knowledge?assistant=assistant-1");
  });

  it("shows a distinct state for filtered results with a clear-filters action", () => {
    render(<NoFilterResultsState assistantId="assistant-1" />);
    expect(screen.getByRole("heading", { name: "No review items match these filters" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Clear all filters" }).getAttribute("href")).toBe("/review/unanswered?assistant=assistant-1");
  });

  it("shows a not-found state that links back to the queue", () => {
    render(<ReviewItemNotFoundState assistantId="assistant-1" />);
    expect(screen.getByRole("heading", { name: "Review item not found" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to review queue" }).getAttribute("href")).toBe("/review/unanswered?assistant=assistant-1");
  });
});
