import { describe, expect, it, vi } from "vitest";
import { bootstrapWidgetShell, renderShell, setShellFailed, setShellReady } from "../src/bootstrap";

describe("iframe shell", () => {
  it("renders accessible loading, ready, and failure states", () => {
    document.body.innerHTML = `<div id="app"></div>`;
    const root = document.getElementById("app");
    expect(root).not.toBeNull();
    if (!root) return;
    renderShell(root);
    expect(root.getAttribute("role")).toBe("status");
    expect(root.getAttribute("aria-live")).toBe("polite");
    expect(root.textContent).toContain("Loading widget");
    setShellReady(root);
    expect(root.textContent).toContain("Widget ready");
    setShellFailed(root);
    expect(root.textContent).toContain("Widget unavailable");
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
