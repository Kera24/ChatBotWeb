import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import vm from "node:vm";
import { gzipSync } from "node:zlib";

import { describe, expect, it } from "vitest";

describe("build artifacts", () => {
  const dist = join(process.cwd(), "dist");

  it("emits ESM, IIFE, declarations, and source maps", () => {
    for (const file of ["index.js", "yoranix-widget-sdk.global.js", "index.d.ts", "index.js.map", "yoranix-widget-sdk.global.js.map"]) {
      expect(existsSync(join(dist, file)), `${file} should exist`).toBe(true);
    }
  });

  it("supports ESM dynamic import", async () => {
    const mod = await import(join(dist, "index.js"));

    expect(mod.SDK_MAJOR_VERSION).toBe(1);
    expect(typeof mod.validateWidgetSDKConfig).toBe("function");
  });

  it("exposes an IIFE foundation namespace without Node built-ins", () => {
    const source = readFileSync(join(dist, "yoranix-widget-sdk.global.js"), "utf8");
    const sandbox: Record<string, unknown> = {};

    vm.runInNewContext(source, sandbox);

    expect(source).not.toMatch(/node:|require\(|process\.env/);
    expect(sandbox.YoranixWidgetSDK).toBeDefined();
  });

  it("passes initial gzip size budgets", () => {
    const esm = gzipSync(readFileSync(join(dist, "index.js"))).byteLength;
    const iife = gzipSync(readFileSync(join(dist, "yoranix-widget-sdk.global.js"))).byteLength;

    expect(esm).toBeLessThanOrEqual(10 * 1024);
    expect(iife).toBeLessThanOrEqual(12 * 1024);
    expect(statSync(join(dist, "index.js")).size).toBeGreaterThan(0);
  });
});