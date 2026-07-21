import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { assertSemver, normalizeOrigin, validateReleaseConfig } from "../scripts/release-config.mjs";

describe("widget release configuration", () => {
  it("validates production-like HTTPS origins and separates versions", () => {
    const config = validateReleaseConfig({
      WIDGET_RELEASE_ENVIRONMENT: "production",
      WIDGET_RELEASE_CHANNEL: "pilot",
      WIDGET_PUBLIC_ORIGIN: "https://widget.example.com",
      WIDGET_PUBLIC_API_ORIGIN: "https://widget-api.example.com",
      WIDGET_SDK_PUBLIC_ORIGIN: "https://cdn.example.com",
    });

    expect(config.sdk_version).toMatch(/^\d+\.\d+\.\d+/);
    expect(config.sdk_major).toBe(1);
    expect(config.protocol_major).toBe(1);
    expect(config.api_version).toBe("v1");
    expect(config.origins.WIDGET_PUBLIC_ORIGIN).toBe("https://widget.example.com");
  });

  it("rejects localhost, credentials, paths, and insecure production origins", () => {
    expect(() => normalizeOrigin("http://localhost:4300", { productionLike: true, name: "WIDGET_PUBLIC_ORIGIN" })).toThrow(/HTTPS|localhost/);
    expect(() => normalizeOrigin("https://user:pass@widget.example.com", { productionLike: true, name: "WIDGET_PUBLIC_ORIGIN" })).toThrow(/credentials/);
    expect(() => normalizeOrigin("https://widget.example.com/embed", { productionLike: true, name: "WIDGET_PUBLIC_ORIGIN" })).toThrow(/origin without path/);
    expect(() => normalizeOrigin("http://widget.example.com", { productionLike: true, name: "WIDGET_PUBLIC_ORIGIN" })).toThrow(/HTTPS/);
  });

  it("keeps semantic SDK version validation authoritative", () => {
    expect(() => assertSemver("0.1.0-foundation.0")).not.toThrow();
    expect(() => assertSemver("1.2.3")).not.toThrow();
    expect(() => assertSemver("v1.2.3")).toThrow(/semantic version/);
  });

  it("defines safe provider-neutral header policies", () => {
    const headers = JSON.parse(readFileSync(resolve(process.cwd(), "../../deployment/widget/headers.json"), "utf8"));
    const byName = Object.fromEntries(headers.policies.map((policy) => [policy.name, policy]));

    expect(byName.sdk_immutable_semver.cache_control).toContain("immutable");
    expect(byName.sdk_major_alias.cache_control).toContain("must-revalidate");
    expect(byName.iframe_html.cache_control).toBe("no-cache");
    expect(byName.iframe_hashed_assets.cache_control).toContain("immutable");
    expect(byName.iframe_html.headers["Content-Security-Policy"]).not.toContain("unsafe-eval");
    expect(byName.iframe_html.headers["Permissions-Policy"]).toContain("camera=()");
    expect(byName.sdk_immutable_semver.headers["Cross-Origin-Resource-Policy"]).toBe("cross-origin");
  });
});
