// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createProtocolEnvelope,
  createPublicAPI,
  installGlobalAPI,
  readConfigFromScriptElement,
  WIDGET_PROTOCOL_SOURCE_IFRAME,
  type YoranixWidgetPublicAPI,
} from "../src";

const config = {
  widgetKey: "wpk_dev_1234567890abcdef",
  environment: "development" as const,
  iframeHost: "http://localhost:4301",
};

let api: YoranixWidgetPublicAPI | undefined;

afterEach(async () => {
  await api?.destroy().catch(() => undefined);
  api = undefined;
  document.body.innerHTML = "";
  document.head.innerHTML = "";
  Reflect.deleteProperty(window, "YoranixWidget");
});

function iframeWindow(): Window {
  const iframe = document.getElementById("yoranix-widget-iframe") as HTMLIFrameElement | null;
  expect(iframe).not.toBeNull();
  expect(iframe?.src).not.toContain("session");
  expect(iframe?.src).not.toContain("tenant");
  const win = iframe?.contentWindow;
  expect(win).not.toBeNull();
  return win as Window;
}

function sendFromIframe(type: "iframe_ready" | "widget_ready" | "widget_state_changed" | "resize_request", payload: Record<string, unknown>): void {
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: "http://localhost:4301",
      source: iframeWindow(),
      data: createProtocolEnvelope(type, WIDGET_PROTOCOL_SOURCE_IFRAME, payload),
    }),
  );
}

async function completeHandshake(publicApi = api): Promise<void> {
  if (!publicApi) throw new Error("missing api");
  sendFromIframe("iframe_ready", { protocolVersion: 1 });
  sendFromIframe("widget_ready", { state: "ready_closed" });
  await publicApi.whenReady();
}

describe("widget runtime lifecycle", () => {
  it("initialises, mounts one iframe, completes handshake, and resolves readiness", async () => {
    api = createPublicAPI(window, document);
    const ready = api.init(config);
    await Promise.resolve();
    const iframe = document.getElementById("yoranix-widget-iframe") as HTMLIFrameElement | null;
    expect(iframe).not.toBeNull();
    expect(iframe?.getAttribute("sandbox")).toContain("allow-scripts");
    expect(iframe?.title).toBe("Yoranix chat widget");
    await completeHandshake(api);
    await ready;
    expect(api.isReady()).toBe(true);
    expect(api.isOpen()).toBe(false);
    expect(document.querySelectorAll("iframe")).toHaveLength(1);
  });

  it("reuses identical init and rejects conflicting init", async () => {
    api = createPublicAPI(window, document);
    const first = api.init(config);
    await Promise.resolve();
    await completeHandshake(api);
    await first;
    await expect(api.init(config)).resolves.toBeUndefined();
    await expect(api.init({ ...config, widgetKey: "wpk_dev_abcdefabcdef1234" })).rejects.toMatchObject({ code: "duplicate_initialisation" });
    expect(document.querySelectorAll("iframe")).toHaveLength(1);
  });

  it("opens, closes, toggles, emits events, and restores focus after acknowledgements", async () => {
    document.body.innerHTML = `<button id="before">Before</button>`;
    const button = document.getElementById("before") as HTMLButtonElement;
    button.focus();
    api = createPublicAPI(window, document);
    const initPromise = api.init(config);
    await Promise.resolve();
    await completeHandshake(api);
    await initPromise;
    const events: string[] = [];
    api.on("opened", () => events.push("opened"));
    api.on("closed", () => events.push("closed"));
    const openPromise = api.open();
    await Promise.resolve();
    sendFromIframe("widget_state_changed", { state: "ready_open" });
    await openPromise;
    expect(api.isOpen()).toBe(true);
    expect(document.getElementById("yoranix-widget-root")?.getAttribute("data-yoranix-state")).toBe("open");
    const closePromise = api.close();
    await Promise.resolve();
    sendFromIframe("widget_state_changed", { state: "ready_closed" });
    await closePromise;
    expect(api.isOpen()).toBe(false);
    expect(document.activeElement).toBe(button);
    expect(events).toEqual(["opened", "closed"]);
  });

  it("applies bounded resize requests and ignores invalid protocol sources", async () => {
    api = createPublicAPI(window, document);
    const initPromise = api.init(config);
    await Promise.resolve();
    await completeHandshake(api);
    await initPromise;
    sendFromIframe("resize_request", { width: 99999, height: 99999 });
    const root = document.getElementById("yoranix-widget-root") as HTMLElement;
    expect(Number.parseInt(root.style.width, 10)).toBeLessThanOrEqual(720);
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "http://evil.example",
        source: iframeWindow(),
        data: createProtocolEnvelope("widget_state_changed", WIDGET_PROTOCOL_SOURCE_IFRAME, { state: "ready_open" }),
      }),
    );
    expect(api.isOpen()).toBe(false);
  });

  it("destroys cleanly and permits a new runtime", async () => {
    api = createPublicAPI(window, document);
    const initPromise = api.init(config);
    await Promise.resolve();
    await completeHandshake(api);
    await initPromise;
    await api.destroy();
    expect(document.getElementById("yoranix-widget-root")).toBeNull();
    expect(api.getState()).toBe("uninitialised");
    const secondInitPromise = api.init(config);
    await Promise.resolve();
    await completeHandshake(api);
    await secondInitPromise;
    expect(document.querySelectorAll("iframe")).toHaveLength(1);
  });

  it("rejects commands before init with safe errors", async () => {
    api = createPublicAPI(window, document);
    await expect(api.open()).rejects.toMatchObject({ code: "sdk_not_ready" });
    await expect(api.whenReady()).rejects.toMatchObject({ code: "sdk_not_ready" });
  });

  it("does not log debug output when disabled", async () => {
    const spy = vi.spyOn(console, "debug").mockImplementation(() => undefined);
    api = createPublicAPI(window, document);
    const initPromise = api.init(config);
    await Promise.resolve();
    await completeHandshake(api);
    await initPromise;
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});

describe("global and auto init", () => {
  it("installs global API without overwriting unrelated globals", () => {
    Object.defineProperty(window, "YoranixWidget", { value: { existing: true }, configurable: true });
    expect(installGlobalAPI(window, document)).toBe(false);
    expect((window as unknown as { YoranixWidget: { existing: boolean } }).YoranixWidget.existing).toBe(true);
  });

  it("parses approved script data attributes", () => {
    const script = document.createElement("script");
    script.dataset.widgetKey = "wpk_dev_1234567890abcdef";
    script.dataset.environment = "development";
    script.dataset.initialOpen = "true";
    script.dataset.mountMode = "floating";
    script.dataset.locale = "en-AU";
    script.dataset.debug = "false";
    const parsed = readConfigFromScriptElement(script);
    expect(parsed).toMatchObject({ widgetKey: "wpk_dev_1234567890abcdef", initialOpen: true, localeHint: "en-AU" });
    expect(parsed).not.toHaveProperty("sessionToken");
  });

  it("auto initialises once from currentScript when a widget key is present", async () => {
    const script = document.createElement("script");
    script.dataset.widgetKey = "wpk_dev_1234567890abcdef";
    script.dataset.environment = "development";
    Object.defineProperty(document, "currentScript", { value: script, configurable: true });
    expect(installGlobalAPI(window, document)).toBe(true);
    api = (window as unknown as { YoranixWidget: YoranixWidgetPublicAPI }).YoranixWidget;
    await Promise.resolve();
    await completeHandshake(api);
    expect(api.isReady()).toBe(true);
    expect(document.querySelectorAll("iframe")).toHaveLength(1);
  });
});


