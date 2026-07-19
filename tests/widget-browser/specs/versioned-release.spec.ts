import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { HOST_ORIGIN, WIDGET_ORIGIN, API_ORIGIN, startWidgetBrowserServers } from "../servers/test-servers";

const repoRoot = resolve(fileURLToPath(new URL("../../../", import.meta.url)));

test.describe("@release versioned release artifacts", () => {
  test("load through the major SDK alias and complete the iframe/API flow", async ({ page }) => {
    process.env.WIDGET_BROWSER_RELEASE_ARTIFACTS = "1";
    const manifest = JSON.parse(readFileSync(resolve(repoRoot, "artifacts/widget-release/manifest.json"), "utf8"));
    const servers = await startWidgetBrowserServers();
    try {
      await page.goto(`${HOST_ORIGIN}/release`);
      await page.waitForFunction(() => Boolean(window.YoranixWidget?.isReady?.()));
      await page.evaluate(() => window.YoranixWidget.open());

      const iframe = page.frame({ url: new RegExp(`^${WIDGET_ORIGIN.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/embed/`) });
      expect(iframe).toBeTruthy();
      await expect(page.locator("iframe")).toHaveCount(1);
      expect(manifest.major_alias_path).toBe(`/widget-sdk/v${manifest.sdk_major}/loader.js`);
      expect(manifest.immutable_loader_path).toBe(`/widget-sdk/v${manifest.sdk_version}/loader.js`);
      expect(manifest.protocol_major).toBe(1);

      const apiOrigins = servers.apiRequests.map((request) => request.origin);
      expect(apiOrigins).toContain(WIDGET_ORIGIN);
      expect(apiOrigins).not.toContain(HOST_ORIGIN);
      expect(servers.origins.api).toBe(API_ORIGIN);
    } finally {
      await servers.close();
      delete process.env.WIDGET_BROWSER_RELEASE_ARTIFACTS;
    }
  });
});
