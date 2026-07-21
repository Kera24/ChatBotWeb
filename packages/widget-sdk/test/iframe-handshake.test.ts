import { describe, expect, it } from "vitest";
import { assertValidWidgetSDKConfig, buildInitialisePayload, buildWidgetIframeUrl, normaliseOrigin, SDKHandshakeController, WidgetSDKError } from "../src";
import { createProtocolEnvelope, WIDGET_PROTOCOL_SOURCE_IFRAME } from "../src/protocol";

function developmentConfig() {
  return assertValidWidgetSDKConfig({
    widgetKey: "wpk_dev_1234567890abcdef",
    environment: "development",
    iframeHost: "http://localhost:4301",
  });
}

class FakeWindow {
  listeners: Array<(event: MessageEvent) => void> = [];
  posted: Array<{ message: unknown; targetOrigin: string }> = [];
  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    if (type === "message") this.listeners.push(listener);
  }
  removeEventListener(type: string, listener: (event: MessageEvent) => void) {
    if (type === "message") this.listeners = this.listeners.filter((entry) => entry !== listener);
  }
  postMessage(message: unknown, targetOrigin: string) {
    this.posted.push({ message, targetOrigin });
  }
  dispatch(event: Partial<MessageEvent>) {
    this.listeners.forEach((listener) => listener(event as MessageEvent));
  }
}

describe("iframe URL builder", () => {
  it("builds a bounded iframe URL with parent origin and no session data", () => {
    const built = buildWidgetIframeUrl(developmentConfig(), "http://localhost:3000");
    expect(built).not.toBeInstanceOf(WidgetSDKError);
    if (built instanceof WidgetSDKError) throw built;
    expect(built.url).toContain("/embed/wpk_dev_1234567890abcdef");
    expect(built.url).toContain("parent_origin=http%3A%2F%2Flocalhost%3A3000");
    expect(built.url).not.toContain("session");
    expect(built.iframeOrigin).toBe("http://localhost:4301");
  });

  it("rejects unsafe parent origins", () => {
    expect(normaliseOrigin("null", "development")).toBeInstanceOf(WidgetSDKError);
    expect(normaliseOrigin("http://user:pass@example.com", "development")).toBeInstanceOf(WidgetSDKError);
    expect(normaliseOrigin("http://example.com", "production")).toBeInstanceOf(WidgetSDKError);
  });
});

describe("SDK handshake controller", () => {
  it("validates origin and source before sending initialise", () => {
    const parent = new FakeWindow();
    const iframe = new FakeWindow();
    const payload = buildInitialisePayload({
      widgetKey: "wpk_dev_1234567890abcdef",
      parentOrigin: "http://localhost:3000",
      sdkVersion: "0.1.0-foundation.0",
      environment: "development",
      initialOpen: false,
      mountMode: "floating",
      debug: false,
    });
    const controller = new SDKHandshakeController({
      parentWindow: parent as unknown as Window,
      iframeWindow: iframe as unknown as Window,
      iframeOrigin: "http://localhost:4301",
      initialisePayload: payload,
      readyTimeoutMs: 100,
      ackTimeoutMs: 100,
    });
    controller.start();
    parent.dispatch({
      origin: "http://localhost:4301",
      source: iframe as unknown as MessageEventSource,
      data: createProtocolEnvelope("iframe_ready", WIDGET_PROTOCOL_SOURCE_IFRAME, { protocolVersion: 1 }),
    });
    expect(controller.state).toBe("initialising");
    expect(iframe.posted).toHaveLength(1);
    expect(iframe.posted[0]?.targetOrigin).toBe("http://localhost:4301");
  });

  it("rejects wrong iframe origin", () => {
    const parent = new FakeWindow();
    const iframe = new FakeWindow();
    const errors: unknown[] = [];
    const controller = new SDKHandshakeController({
      parentWindow: parent as unknown as Window,
      iframeWindow: iframe as unknown as Window,
      iframeOrigin: "https://widget.yoranix.com",
      initialisePayload: buildInitialisePayload({
        widgetKey: "wpk_live_1234567890abcdef",
        parentOrigin: "https://example.com",
        sdkVersion: "0.1.0-foundation.0",
        environment: "production",
        initialOpen: false,
        mountMode: "floating",
        debug: false,
      }),
      onError: (error) => errors.push(error),
    });
    controller.start();
    parent.dispatch({ origin: "https://evil.example", source: iframe as unknown as MessageEventSource, data: {} });
    expect(controller.state).toBe("failed");
    expect(errors).toHaveLength(1);
  });
});

