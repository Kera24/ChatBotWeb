import { cleanup, fireEvent, render, screen } from "@testing-library/preact";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WidgetApp } from "../src/ui/components/widget-app";
import type { ConversationSnapshot } from "../src/state/conversation-state";
import type { WidgetStateSnapshot } from "../src/state/widget-state";
import { validConfig } from "./fixtures";

const readySnapshot: WidgetStateSnapshot = Object.freeze({
  bootstrapStatus: "ready",
  config: Object.freeze({ status: "ready", data: validConfig, etag: "etag_1" }),
  session: Object.freeze({ status: "none", expiresAt: null, absoluteExpiresAt: null, remainingMessages: null, configurationVersion: null }),
  message: Object.freeze({ status: "idle", lastResponse: null }),
  lastError: null,
});

const emptyConversation: ConversationSnapshot = Object.freeze({ entries: Object.freeze([]), activeLogicalSendId: null, announcement: null, revision: 0 });

afterEach(() => cleanup());

describe("Widget B2 welcome and message presentation", () => {
  it("renders configured welcome, suggested questions, and composer", () => {
    render(<WidgetApp shellState="open" snapshot={readySnapshot} conversation={emptyConversation} systemDark={false} />);
    expect(screen.getByRole("heading", { name: "Ask Yoranix" })).toBeTruthy();
    expect(screen.getByText("Hello")).toBeTruthy();
    expect(screen.getByRole("group", { name: "Suggested questions" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /What can you do/ })).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeTruthy();
  });

  it("sends a suggestion directly and disables suggestions while busy", () => {
    const onSuggestionSelect = vi.fn();
    render(<WidgetApp shellState="open" snapshot={readySnapshot} conversation={{ ...emptyConversation, activeLogicalSendId: "send_1" }} systemDark={false} onSuggestionSelect={onSuggestionSelect} />);
    expect(screen.getByRole("button", { name: /What can you do/ }).hasAttribute("disabled")).toBe(true);
  });

  it("renders user, preparation, answered, fallback, low-confidence, and failed states", () => {
    const conversation: ConversationSnapshot = Object.freeze({
      activeLogicalSendId: null,
      announcement: "Answer ready.",
      revision: 1,
      entries: Object.freeze([
        Object.freeze({ id: "u1", role: "user", createdAt: "2026-07-18T00:00:00Z", status: "sent", content: "Question" }),
        Object.freeze({ id: "a1", role: "assistant", createdAt: "2026-07-18T00:00:01Z", status: "answered", content: "Answer" }),
        Object.freeze({ id: "a2", role: "assistant", createdAt: "2026-07-18T00:00:02Z", status: "fallback", content: "I could not find this." }),
        Object.freeze({ id: "a3", role: "assistant", createdAt: "2026-07-18T00:00:03Z", status: "low_confidence", content: "This may help." }),
        Object.freeze({ id: "a4", role: "assistant", createdAt: "2026-07-18T00:00:04Z", status: "preparing", content: "Checking" }),
        Object.freeze({ id: "a5", role: "assistant", createdAt: "2026-07-18T00:00:05Z", status: "failed", content: "Please try again.", retry: Object.freeze({ retryable: true, logicalSendId: "send_5" }) }),
      ]),
    });
    render(<WidgetApp shellState="open" snapshot={readySnapshot} conversation={conversation} systemDark={false} />);
    expect(screen.getByLabelText("You said")).toBeTruthy();
    expect(screen.getAllByText("Answer").length).toBeGreaterThan(0);
    expect(screen.getByText("Fallback answer")).toBeTruthy();
    expect(screen.getByText("Low confidence")).toBeTruthy();
    expect(screen.getByText("Checking the available information")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Retry/ })).toBeTruthy();
  });

  it("renders malicious plain text inertly", () => {
    const conversation: ConversationSnapshot = Object.freeze({
      activeLogicalSendId: null,
      announcement: null,
      revision: 1,
      entries: Object.freeze([
        Object.freeze({ id: "a1", role: "assistant", createdAt: "2026-07-18T00:00:01Z", status: "answered", content: '<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n[a](javascript:alert(1))' }),
      ]),
    });
    render(<WidgetApp shellState="open" snapshot={readySnapshot} conversation={conversation} systemDark={false} />);
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelectorAll("img")).toHaveLength(1);
    expect(document.querySelector("main a")).toBeNull();
    expect(document.body.textContent).toContain("<script>alert(1)</script>");
  });

  it("invokes retry callback for retryable failures", () => {
    const onRetry = vi.fn();
    const conversation: ConversationSnapshot = Object.freeze({
      activeLogicalSendId: null,
      announcement: null,
      revision: 1,
      entries: Object.freeze([
        Object.freeze({ id: "a1", role: "assistant", createdAt: "2026-07-18T00:00:01Z", status: "failed", content: "Try again", retry: Object.freeze({ retryable: true, logicalSendId: "send_1" }) }),
      ]),
    });
    render(<WidgetApp shellState="open" snapshot={readySnapshot} conversation={conversation} systemDark={false} onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
    expect(onRetry).toHaveBeenCalledWith("send_1");
  });
});
