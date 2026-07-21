import { describe, expect, it } from "vitest";

import { assertValidWidgetSDKConfig, validateWidgetSDKConfig } from "../src/config";
import { WidgetSDKError } from "../src/errors";

const DEV_KEY = "wpk_dev_abcdefghijklmnopqrstuvwxyz";
const STG_KEY = "wpk_stg_abcdefghijklmnopqrstuvwxyz";
const LIVE_KEY = "wpk_live_abcdefghijklmnopqrstuvwxyz";

describe("validateWidgetSDKConfig", () => {
  it("accepts a valid development config with overrides", () => {
    const input = {
      widgetKey: DEV_KEY,
      environment: "development",
      initialOpen: true,
      mountMode: "floating",
      localeHint: "en-AU",
      debug: true,
      sdkHost: "http://localhost:4300/",
      iframeHost: "http://127.0.0.1:4301/embed",
      nonce: "abc123+/=",
    };

    const result = validateWidgetSDKConfig(input);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.config.hosts.sdkHost).toBe("http://localhost:4300");
      expect(result.config.hosts.iframeHost).toBe("http://127.0.0.1:4301/embed");
      expect(result.config.debug).toBe(true);
    }
    expect(input.widgetKey).toBe(DEV_KEY);
  });

  it("accepts staging and production defaults", () => {
    expect(validateWidgetSDKConfig({ widgetKey: STG_KEY, environment: "staging" }).ok).toBe(true);
    const production = validateWidgetSDKConfig({ widgetKey: LIVE_KEY });
    expect(production.ok).toBe(true);
    if (production.ok) {
      expect(production.config.environment).toBe("production");
      expect(production.config.hosts.iframeHost).toBe("https://widget.yoranix.com");
    }
  });

  it("rejects missing and malformed widget keys", () => {
    expect(validateWidgetSDKConfig({}).ok).toBe(false);
    const malformed = validateWidgetSDKConfig({ widgetKey: "wpk_live_short" });
    expect(malformed.ok).toBe(false);
    if (!malformed.ok) {
      expect(malformed.error.code).toBe("invalid_widget_key");
    }
  });

  it("rejects key and environment mismatch", () => {
    const result = validateWidgetSDKConfig({ widgetKey: LIVE_KEY, environment: "development" });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.code).toBe("environment_mismatch");
    }
  });

  it("rejects production host overrides and accepts development host overrides", () => {
    const production = validateWidgetSDKConfig({ widgetKey: LIVE_KEY, sdkHost: "https://example.com" });
    const development = validateWidgetSDKConfig({ widgetKey: DEV_KEY, sdkHost: "http://localhost:4300" });

    expect(production.ok).toBe(false);
    if (!production.ok) {
      expect(production.error.code).toBe("insecure_host");
    }
    expect(development.ok).toBe(true);
  });

  it("rejects insecure and userinfo hosts", () => {
    const insecure = validateWidgetSDKConfig({ widgetKey: DEV_KEY, sdkHost: "http://example.com" });
    const userinfo = validateWidgetSDKConfig({ widgetKey: DEV_KEY, sdkHost: "https://user:pass@example.com" });

    expect(insecure.ok).toBe(false);
    expect(userinfo.ok).toBe(false);
  });

  it("rejects invalid locale, debug outside development, bad mount mode, and unknown fields", () => {
    expect(validateWidgetSDKConfig({ widgetKey: DEV_KEY, localeHint: "this-is-too-long-for-a-locale-tag-value" }).ok).toBe(false);
    expect(validateWidgetSDKConfig({ widgetKey: LIVE_KEY, debug: true }).ok).toBe(false);
    expect(validateWidgetSDKConfig({ widgetKey: DEV_KEY, mountMode: "popup" }).ok).toBe(false);
    expect(validateWidgetSDKConfig({ widgetKey: DEV_KEY, organisationId: "org_1" }).ok).toBe(false);
  });

  it("does not expose tenant/session/model fields in validated config", () => {
    const config = assertValidWidgetSDKConfig({ widgetKey: DEV_KEY });

    expect("sessionToken" in config).toBe(false);
    expect("organisationId" in config).toBe(false);
    expect("modelKey" in config).toBe(false);
  });

  it("throws typed errors from assertValidWidgetSDKConfig", () => {
    expect(() => assertValidWidgetSDKConfig({ widgetKey: "bad" })).toThrow(WidgetSDKError);
  });
});