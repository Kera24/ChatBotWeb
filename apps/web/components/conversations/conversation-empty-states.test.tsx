import { describe, expect, it } from "vitest";

import { render, screen } from "../../test/test-utils";
import {
  ConversationNotFoundState,
  ConversationWrongAssistantState,
  NoAssistantSelectedState,
  NoConversationsState,
  NoFilterResultsState,
} from "./conversation-empty-states";

describe("conversation empty states", () => {
  it("prompts the user to select an assistant", () => {
    render(<NoAssistantSelectedState />);
    expect(screen.getByRole("heading", { name: "No assistant selected" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to My Assistants" }).getAttribute("href")).toBe("/dashboard");
  });

  it("shows a no-activity state with real navigation actions", () => {
    render(<NoConversationsState assistantId="assistant-1" />);
    expect(screen.getByRole("heading", { name: "No conversations have been recorded" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open Chat Playground" }).getAttribute("href")).toBe("/chatbot?assistant=assistant-1");
    expect(screen.getByRole("link", { name: "Add knowledge" }).getAttribute("href")).toBe("/knowledge?assistant=assistant-1");
  });

  it("shows a distinct state for filtered results with a clear-filters action", () => {
    render(<NoFilterResultsState assistantId="assistant-1" />);
    expect(screen.getByRole("heading", { name: "No conversations match these filters" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Clear all filters" }).getAttribute("href")).toBe("/conversations?assistant=assistant-1");
  });

  it("shows a not-found state that links back to the list", () => {
    render(<ConversationNotFoundState assistantId="assistant-1" />);
    expect(screen.getByRole("heading", { name: "Conversation not found" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to conversations" }).getAttribute("href")).toBe("/conversations?assistant=assistant-1");
  });

  it("shows an alert when a conversation belongs to a different assistant", () => {
    render(<ConversationWrongAssistantState assistantId="assistant-1" />);
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "This conversation belongs to a different assistant" })).toBeTruthy();
  });
});
