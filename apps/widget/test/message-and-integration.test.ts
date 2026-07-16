import { createProtocolEnvelope, WIDGET_PROTOCOL_SOURCE_LOADER } from "@yoranix/widget-sdk";
import { describe, expect, it, vi } from "vitest";
import { IframeHandshakeController } from "../src/handshake";
import { assertNoSessionToken } from "../src/security/token-redaction";
import { validSession } from "./fixtures";

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
    assertNoSessionToken(message);
    this.posted.push({ message, targetOrigin });
  }
  dispatch(event: Partial<MessageEvent>) {
    this.listeners.forEach((listener) => listener(event as MessageEvent));
  }
}

const initialisePayload = {
  widgetKey: "wpk_dev_1234567890abcdef",
  parentOrigin: "http://localhost:3000",
  sdkVersion: "0.1.0-foundation.0",
  protocolVersion: 1,
  environment: "development" as const,
  initialOpen: false,
  mountMode: "floating" as const,
  debug: false,
};

describe("iframe API lifecycle integration", () => {
  it("waits for async config bootstrap before widget_ready", async () => {
    const parent = new FakeWindow();
    const self = new FakeWindow();
    let releaseBootstrap: (() => void) | undefined;
    const bootstrap = new Promise<void>((resolve) => {
      releaseBootstrap = resolve;
    });
    const controller = new IframeHandshakeController({
      parentOrigin: "http://localhost:3000",
      parentWindow: parent,
      selfWindow: self as unknown as Window,
      onInitialise: () => bootstrap,
    });
    controller.start();
    self.dispatch({
      origin: "http://localhost:3000",
      source: parent as unknown as MessageEventSource,
      data: createProtocolEnvelope("initialise", WIDGET_PROTOCOL_SOURCE_LOADER, initialisePayload),
    });

    expect(parent.posted.some((entry) => JSON.stringify(entry.message).includes("widget_ready"))).toBe(false);
    releaseBootstrap?.();
    await Promise.resolve();
    await Promise.resolve();
    expect(parent.posted.some((entry) => JSON.stringify(entry.message).includes("widget_ready"))).toBe(true);
    expect(JSON.stringify(parent.posted)).not.toContain(validSession.session_token);
    expect(JSON.stringify(parent.posted)).not.toContain("Safe answer");
  });

  it("sends generic handshake error when config bootstrap fails", async () => {
    const parent = new FakeWindow();
    const self = new FakeWindow();
    const onError = vi.fn();
    const controller = new IframeHandshakeController({
      parentOrigin: "http://localhost:3000",
      parentWindow: parent,
      selfWindow: self as unknown as Window,
      onInitialise: async () => {
        throw new Error("config failed with hidden details");
      },
      onError,
    });
    controller.start();
    self.dispatch({
      origin: "http://localhost:3000",
      source: parent as unknown as MessageEventSource,
      data: createProtocolEnvelope("initialise", WIDGET_PROTOCOL_SOURCE_LOADER, initialisePayload),
    });
    await Promise.resolve();
    await Promise.resolve();

    expect(controller.lifecycle.state).toBe("failed");
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ code: "safe_internal_error" }));
    expect(JSON.stringify(parent.posted)).not.toContain("config failed");
  });
});