import { createProtocolEnvelope, WIDGET_PROTOCOL_SOURCE_LOADER } from "@yoranix/widget-sdk";
import { describe, expect, it } from "vitest";
import { IframeHandshakeController } from "../src/handshake";
import { sendToParent } from "../src/protocol";

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

const initialisePayload = {
  widgetKey: "wpk_dev_1234567890abcdef",
  parentOrigin: "http://localhost:3000",
  sdkVersion: "0.1.0-foundation.0",
  protocolVersion: 1,
  environment: "development",
  initialOpen: false,
  mountMode: "floating",
  debug: false,
};

describe("iframe handshake", () => {
  it("runs ready to initialise to widget_ready using exact target origin", () => {
    const parent = new FakeWindow();
    const self = new FakeWindow();
    const controller = new IframeHandshakeController({
      parentOrigin: "http://localhost:3000",
      parentWindow: parent,
      selfWindow: self as unknown as Window,
    });
    controller.start();
    expect(parent.posted[0]?.targetOrigin).toBe("http://localhost:3000");
    self.dispatch({
      origin: "http://localhost:3000",
      source: parent as unknown as MessageEventSource,
      data: createProtocolEnvelope("initialise", WIDGET_PROTOCOL_SOURCE_LOADER, initialisePayload),
    });
    expect(controller.lifecycle.state).toBe("ready_closed");
    expect(parent.posted[parent.posted.length - 1]?.targetOrigin).toBe("http://localhost:3000");
  });

  it("rejects wrong parent origin and duplicate initialise", () => {
    const parent = new FakeWindow();
    const self = new FakeWindow();
    const controller = new IframeHandshakeController({
      parentOrigin: "http://localhost:3000",
      parentWindow: parent,
      selfWindow: self as unknown as Window,
    });
    controller.start();
    self.dispatch({
      origin: "http://evil.example",
      source: parent as unknown as MessageEventSource,
      data: createProtocolEnvelope("initialise", WIDGET_PROTOCOL_SOURCE_LOADER, initialisePayload),
    });
    expect(controller.lifecycle.state).toBe("failed");
  });

  it("rejects wildcard target origins in protocol helper", () => {
    expect(() => sendToParent(new FakeWindow(), createProtocolEnvelope("iframe_ready", "yoranix-iframe", { protocolVersion: 1 }), "*")).toThrow();
  });
});

