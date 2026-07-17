import { cleanup, fireEvent, render, screen } from "@testing-library/preact";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WidgetApiError } from "../src/api/errors";
import { ConversationOrchestrator, validateComposerMessage, PUBLIC_MESSAGE_MAX_CHARACTERS } from "../src/services/conversation-orchestrator";
import { ConversationStore, type ConversationSnapshot } from "../src/state/conversation-state";
import { WidgetApp } from "../src/ui/components/widget-app";
import type { WidgetStateSnapshot } from "../src/state/widget-state";
import { validConfig, validMessage } from "./fixtures";

const readySnapshot: WidgetStateSnapshot = Object.freeze({
  bootstrapStatus: "ready",
  config: Object.freeze({ status: "ready", data: validConfig, etag: "etag_1" }),
  session: Object.freeze({ status: "active", expiresAt: "2099-01-01T00:00:00Z", absoluteExpiresAt: "2099-01-01T00:00:00Z", remainingMessages: 2, configurationVersion: 3 }),
  message: Object.freeze({ status: "idle", lastResponse: null }),
  lastError: null,
});

const emptyConversation: ConversationSnapshot = Object.freeze({ entries: Object.freeze([]), activeLogicalSendId: null, announcement: null, revision: 0 });

afterEach(() => cleanup());

describe("Widget B3 composer and citations", () => {
  it("validates composer input without mutating message content", () => {
    expect(validateComposerMessage("   ").ok).toBe(false);
    expect(validateComposerMessage("hello\nthere")).toMatchObject({ ok: true, value: "hello\nthere" });
    expect(validateComposerMessage("x".repeat(PUBLIC_MESSAGE_MAX_CHARACTERS + 1))).toMatchObject({ ok: false, overLimit: true });
  });

  it("submits custom text with Enter and preserves Shift+Enter as newline", () => {
    const onSubmitMessage = vi.fn();
    render(<WidgetApp shellState="open" snapshot={readySnapshot} conversation={emptyConversation} systemDark={false} onSubmitMessage={onSubmitMessage} />);
    const textbox = screen.getByRole("textbox", { name: "Message" }) as HTMLTextAreaElement;
    fireEvent.input(textbox, { target: { value: "hello" } });
    fireEvent.keyDown(textbox, { key: "Enter", shiftKey: true });
    expect(onSubmitMessage).not.toHaveBeenCalled();
    fireEvent.keyDown(textbox, { key: "Enter" });
    expect(onSubmitMessage).toHaveBeenCalledWith("hello");
  });

  it("prevents IME Enter submission", () => {
    const onSubmitMessage = vi.fn();
    render(<WidgetApp shellState="open" snapshot={readySnapshot} conversation={emptyConversation} systemDark={false} onSubmitMessage={onSubmitMessage} />);
    const textbox = screen.getByRole("textbox", { name: "Message" });
    fireEvent.input(textbox, { target: { value: "?????" } });
    fireEvent.compositionStart(textbox);
    fireEvent.keyDown(textbox, { key: "Enter" });
    expect(onSubmitMessage).not.toHaveBeenCalled();
  });

  it("renders validated citations in an accessible disclosure", () => {
    const conversation: ConversationSnapshot = Object.freeze({
      activeLogicalSendId: null,
      announcement: null,
      revision: 1,
      entries: Object.freeze([
        Object.freeze({
          id: "a1",
          role: "assistant",
          createdAt: "2026-07-18T00:00:00Z",
          status: "answered",
          content: "Answer with sources",
          citations: Object.freeze([{ citation_index: 1, source_title: "Policy guide", source_type: "document", page_number: 3, section_title: "Scope", quoted_text: "Approved excerpt" }]),
        }),
      ]),
    });
    render(<WidgetApp shellState="open" snapshot={readySnapshot} conversation={conversation} systemDark={false} />);
    expect(screen.getByText("Sources (1)")).toBeTruthy();
    expect(screen.getByText(/Policy guide/)).toBeTruthy();
    expect(screen.getByText(/page 3/)).toBeTruthy();
    expect(document.querySelector("main a")).toBeNull();
  });

  it("shows rate-limit and session notices without exposing raw codes", () => {
    const rateSnapshot: WidgetStateSnapshot = Object.freeze({ ...readySnapshot, lastError: Object.freeze({ code: "rate_limited", message: "Too many", retryable: true, phase: "message", retryAfterSeconds: 5 }) });
    render(<WidgetApp shellState="open" snapshot={rateSnapshot} conversation={emptyConversation} systemDark={false} />);
    expect(screen.getAllByText(/wait/i).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("rate_limited");
  });
});

describe("ConversationOrchestrator custom sends", () => {
  it("uses the existing message service path for custom text", async () => {
    const store = new ConversationStore();
    const sendMessage = vi.fn().mockResolvedValue(validMessage);
    const orchestrator = new ConversationOrchestrator({ conversationStore: store, messageService: { sendMessage } as never, configProvider: () => validConfig });
    await orchestrator.submitCustomMessage("  Custom question  ");
    expect(sendMessage).toHaveBeenCalledWith("Custom question", { source: "composer" }, expect.stringMatching(/^wid_/));
    expect(JSON.stringify(store.snapshot())).not.toContain("wid_");
  });

  it("allows explicit recovery for invalid sessions without silent resend", async () => {
    const store = new ConversationStore();
    const sendMessage = vi.fn().mockRejectedValueOnce(new WidgetApiError("invalid_session", "message", { retryable: false })).mockResolvedValue(validMessage);
    const orchestrator = new ConversationOrchestrator({ conversationStore: store, messageService: { sendMessage } as never, configProvider: () => validConfig });
    await orchestrator.submitCustomMessage("Retry me");
    expect(sendMessage).toHaveBeenCalledTimes(1);
    const retryId = store.snapshot().entries.find((entry) => entry.retry?.retryable)?.retry?.logicalSendId;
    expect(retryId).toBeTruthy();
    await orchestrator.retry(retryId!);
    expect(sendMessage).toHaveBeenCalledTimes(2);
  });
});
