import { describe, expect, it, vi } from "vitest";
import { bootstrapWidgetShell } from "../src/bootstrap";
import { mountWidgetUi } from "../src/ui/root";
import { WidgetStateStore } from "../src/state/widget-state";
import { validConfig } from "./fixtures";

describe("iframe shell", () => {
  it("renders accessible loading, ready, open, and failure shell states", async () => {
    document.body.innerHTML = `<div id="app"></div>`;
    const root = document.getElementById("app");
    expect(root).not.toBeNull();
    if (!root) return;
    const ui = mountWidgetUi(root);
    expect(root.getAttribute("data-widget-state")).toBe("loading");
    expect(root.textContent).toContain("Open chat");

    const store = new WidgetStateStore();
    ui.attachStore(store);
    store.update({ bootstrapStatus: "ready", config: { status: "ready", data: validConfig, etag: "etag" } });
    ui.setShellState("closed");
    await Promise.resolve();
    expect(root.textContent).toContain("Chat");
    ui.setShellState("open");
    await Promise.resolve();
    expect(root.textContent).toContain("Yoranix");
    expect(root.querySelector('[role="dialog"]')).not.toBeNull();
    ui.setUnavailable();
    await Promise.resolve();
    expect(root.getAttribute("data-widget-state")).toBe("unavailable");
    expect(root.querySelector(".yw-launcher")?.getAttribute("data-unavailable")).toBe("true");
    ui.destroy();
    expect(root.getAttribute("data-widget-state")).toBe("destroyed");
  });

  it("does not call APIs or write storage during bootstrap failure", () => {
    document.body.innerHTML = `<div id="app"></div>`;
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSpy = vi.spyOn(window.sessionStorage.__proto__, "setItem");
    bootstrapWidgetShell(document, window);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSpy).not.toHaveBeenCalled();
    expect(document.body.textContent).not.toContain("message composer");
    fetchSpy.mockRestore();
    storageSpy.mockRestore();
  });
});
