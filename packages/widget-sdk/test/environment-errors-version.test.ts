import { describe, expect, it } from "vitest";

import { resolveWidgetEnvironment, normaliseHostUrl } from "../src/environment";
import { WidgetSDKError, createSDKError } from "../src/errors";
import { PUBLIC_CONFIG_SCHEMA_VERSION, PUBLIC_MESSAGE_SCHEMA_VERSION, SDK_MAJOR_VERSION, SDK_VERSION, WIDGET_PROTOCOL_VERSION } from "../src/version";

describe("environment resolution", () => {
  it("returns immutable normalised default hosts", () => {
    const result = resolveWidgetEnvironment("production");

    expect(result).not.toBeInstanceOf(WidgetSDKError);
    if (!(result instanceof WidgetSDKError)) {
      expect(result.sdkHost).toBe("https://widget.yoranix.com");
      expect(Object.isFrozen(result)).toBe(true);
      expect(() => ((result as { sdkHost: string }).sdkHost = "https://evil.test")).toThrow();
    }
  });

  it("rejects unsupported or insecure hosts", () => {
    expect(normaliseHostUrl("https://user@example.com", "development")).toBeInstanceOf(WidgetSDKError);
    expect(normaliseHostUrl("http://example.com", "production")).toBeInstanceOf(WidgetSDKError);
  });
});

describe("errors and versions", () => {
  it("serialises safe public errors without internal cause", () => {
    const error = createSDKError("invalid_configuration", "configuration", { cause: new Error("secret stack"), safeMetadata: { field: "widgetKey" } });
    const publicError = error.toPublicJSON();

    expect(publicError).toEqual({
      code: "invalid_configuration",
      message: "The widget configuration is invalid.",
      retryable: false,
      phase: "configuration",
      metadata: { field: "widgetKey" },
    });
    expect(JSON.stringify(publicError)).not.toContain("secret stack");
  });

  it("exports independent version constants", () => {
    expect(SDK_VERSION).toMatch(/^0\.1\.0-foundation\.0$/);
    expect(SDK_MAJOR_VERSION).toBe(1);
    expect(WIDGET_PROTOCOL_VERSION).toBe(1);
    expect(PUBLIC_CONFIG_SCHEMA_VERSION).toBe("1.0");
    expect(PUBLIC_MESSAGE_SCHEMA_VERSION).toBe("1.1");
  });
});