import { cleanup, fireEvent, render, screen } from "@testing-library/preact";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WidgetApp } from "../src/ui/components/widget-app";
import type { WidgetStateSnapshot } from "../src/state/widget-state";
import { validConfig } from "./fixtures";

const readySnapshot: WidgetStateSnapshot = Object.freeze({
  bootstrapStatus: "ready",
  config: Object.freeze({ status: "ready", data: validConfig, etag: "etag_1" }),
  session: Object.freeze({ status: "none", expiresAt: null, absoluteExpiresAt: null, remainingMessages: null, configurationVersion: null }),
  message: Object.freeze({ status: "idle", lastResponse: null }),
  lastError: null,
});

const unavailableSnapshot: WidgetStateSnapshot = Object.freeze({
  ...readySnapshot,
  bootstrapStatus: "unavailable",
});

afterEach(() => cleanup());

describe("WidgetApp structural shell", () => {
  it("renders the loading state without message or composer controls", () => {
    render(<WidgetApp shellState="loading" snapshot={null} systemDark={false} />);
    expect(screen.getByRole("button", { name: "Open chat" })).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByText("Safe answer")).toBeNull();
  });

  it("renders ready closed launcher with configured label", () => {
    render(<WidgetApp shellState="closed" snapshot={readySnapshot} systemDark={false} />);
    expect(screen.getByRole("button", { name: "Chat" })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders open panel header viewport and footer shell", () => {
    render(<WidgetApp shellState="open" snapshot={readySnapshot} systemDark={false} />);
    expect(screen.getByRole("dialog", { name: "Yoranix" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Yoranix" })).toBeTruthy();
    expect(screen.getByText("AI assistant")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Chat conversation" })).toBeTruthy();
    expect(screen.getByLabelText("Chat controls area")).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("uses safe fallback names", () => {
    render(<WidgetApp shellState="open" snapshot={null} systemDark={false} />);
    expect(screen.getByRole("heading", { name: "Yoranix assistant" })).toBeTruthy();
  });

  it("exposes close control and open callbacks", () => {
    const onOpen = vi.fn();
    const onClose = vi.fn();
    const { rerender } = render(<WidgetApp shellState="closed" snapshot={readySnapshot} systemDark={false} onOpen={onOpen} onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Chat" }));
    expect(onOpen).toHaveBeenCalledOnce();
    rerender(<WidgetApp shellState="open" snapshot={readySnapshot} systemDark={false} onOpen={onOpen} onClose={onClose} />);
    fireEvent.click(screen.getAllByRole("button", { name: "Close chat" })[0]);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders unavailable state as an alert without stack details", () => {
    render(<WidgetApp shellState="open" snapshot={unavailableSnapshot} systemDark={false} />);
    expect(screen.getAllByRole("alert").map((node) => node.textContent).join(" ")).toContain("temporarily unavailable");
    expect(document.body.textContent).not.toContain("Error:");
  });
});




