import { describe, expect, it, vi } from "vitest";
import { mountWidgetUi } from "../src/ui/root";
import { WidgetStateStore } from "../src/state/widget-state";
import { validConfig } from "./fixtures";

async function flushUi(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe("widget UI lifecycle and theme integration", () => {
  it("applies CSS variables and updates auto theme on system changes", async () => {
    const listeners = new Set<() => void>();
    let matches = false;
    const originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({
        matches,
        media: "(prefers-color-scheme: dark)",
        onchange: null,
        addEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => listeners.add(listener as () => void),
        removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => listeners.delete(listener as () => void),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    document.body.innerHTML = `<div id="app"></div>`;
    const root = document.getElementById("app")!;
    const store = new WidgetStateStore();
    const ui = mountWidgetUi(root);
    const autoConfig = { ...validConfig, widget: { ...validConfig.widget, theme_mode: "auto" } };
    ui.attachStore(store);
    store.update({ bootstrapStatus: "ready", config: { status: "ready", data: autoConfig, etag: "etag" } });
    await flushUi();
    expect(root.style.getPropertyValue("--yw-color-scheme")).toBe("light");
    matches = true;
    for (const listener of listeners) listener();
    await flushUi();
    expect(root.style.getPropertyValue("--yw-color-scheme")).toBe("dark");
    ui.destroy();
    expect(listeners.size).toBe(0);
    Object.defineProperty(window, "matchMedia", { configurable: true, value: originalMatchMedia });
  });

  it("cleans subscriptions after destroy", () => {
    document.body.innerHTML = `<div id="app"></div>`;
    const root = document.getElementById("app")!;
    const store = new WidgetStateStore();
    const ui = mountWidgetUi(root);
    ui.attachStore(store);
    ui.destroy();
    store.update({ bootstrapStatus: "ready", config: { status: "ready", data: validConfig, etag: "etag" } });
    expect(root.getAttribute("data-widget-state")).toBe("destroyed");
    expect(root.textContent).toBe("");
  });

  it("supports left positioning and does not render token-like values", async () => {
    document.body.innerHTML = `<div id="app"></div>`;
    const root = document.getElementById("app")!;
    const store = new WidgetStateStore();
    const ui = mountWidgetUi(root);
    const leftConfig = { ...validConfig, widget: { ...validConfig.widget, position: "bottom-left" } };
    ui.attachStore(store);
    store.update({
      bootstrapStatus: "ready",
      config: { status: "ready", data: leftConfig, etag: "etag" },
      session: { status: "active", expiresAt: "2099-01-01T00:00:00.000Z", absoluteExpiresAt: "2099-01-01T00:00:00.000Z", remainingMessages: 9, configurationVersion: 3 },
    });
    ui.setShellState("open");
    await flushUi();
    expect(root.querySelector(".yw-root--left")).not.toBeNull();
    expect(root.textContent).not.toContain("pss_");
    expect(root.innerHTML).not.toContain("sessionToken");
  });
});
