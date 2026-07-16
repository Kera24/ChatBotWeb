import { describe, expect, it } from "vitest";
import {
  createProtocolEnvelope,
  validateInitialisePayload,
  validateProtocolEnvelope,
  WIDGET_PROTOCOL_SOURCE_IFRAME,
  WIDGET_PROTOCOL_SOURCE_LOADER,
} from "../src";

const validPayload = {
  widgetKey: "wpk_dev_1234567890abcdef",
  parentOrigin: "http://localhost:3000",
  sdkVersion: "0.1.0-foundation.0",
  protocolVersion: 1,
  environment: "development",
  initialOpen: false,
  mountMode: "floating",
  debug: false,
};

describe("widget protocol envelope", () => {
  it("accepts a valid envelope", () => {
    const envelope = createProtocolEnvelope("iframe_ready", WIDGET_PROTOCOL_SOURCE_IFRAME, { protocolVersion: 1 });
    const result = validateProtocolEnvelope(envelope, { expectedSource: WIDGET_PROTOCOL_SOURCE_IFRAME });
    expect(result.ok).toBe(true);
  });

  it("rejects malformed protocol and unsupported versions", () => {
    const envelope = createProtocolEnvelope("iframe_ready", WIDGET_PROTOCOL_SOURCE_IFRAME, { protocolVersion: 1 });
    expect(validateProtocolEnvelope({ ...envelope, protocol: "other" }).ok).toBe(false);
    expect(validateProtocolEnvelope({ ...envelope, version: 99 }).ok).toBe(false);
  });

  it("rejects wrong source, unknown type, oversized and forbidden payloads", () => {
    const envelope = createProtocolEnvelope("iframe_ready", WIDGET_PROTOCOL_SOURCE_IFRAME, { protocolVersion: 1 });
    expect(validateProtocolEnvelope(envelope, { expectedSource: WIDGET_PROTOCOL_SOURCE_LOADER }).ok).toBe(false);
    expect(validateProtocolEnvelope({ ...envelope, type: "chat_message" }).ok).toBe(false);
    expect(validateProtocolEnvelope({ ...envelope, payload: { sessionToken: "secret" } }).ok).toBe(false);
    expect(validateProtocolEnvelope({ ...envelope, payload: { text: "x".repeat(9000) } }).ok).toBe(false);
  });

  it("rejects cyclic or prototype-bearing payloads", () => {
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;
    expect(() => createProtocolEnvelope("iframe_ready", WIDGET_PROTOCOL_SOURCE_IFRAME, cyclic)).toThrow();
    expect(validateProtocolEnvelope({ payload: new Date() }).ok).toBe(false);
  });

  it("validates initialise payload without token or tenant fields", () => {
    expect(validateInitialisePayload(validPayload)).toBe(true);
    expect(validateInitialisePayload({ ...validPayload, sessionToken: "not-allowed" })).toBe(false);
    expect(validateInitialisePayload({ ...validPayload, tenantId: "not-allowed" })).toBe(false);
  });
});
