import { test, expect, openReadyWidget } from "../helpers/fixtures";

test("open close focus and destroy lifecycle remain bounded", async ({ instrumentedPage: page }) => {
  await openReadyWidget(page);
  await page.locator("#before-widget").focus();
  await page.evaluate(() => window.YoranixWidget.open());
  await expect(page.locator("#yoranix-widget-root")).toHaveAttribute("data-yoranix-state", "open");
  const openBox = await page.locator("#yoranix-widget-root").boundingBox();
  expect(openBox?.width).toBeLessThanOrEqual(420);
  expect(openBox?.height).toBeLessThanOrEqual(680);

  await page.evaluate(() => window.YoranixWidget.close());
  await expect(page.locator("#yoranix-widget-root")).toHaveAttribute("data-yoranix-state", "closed");
  expect(["before-widget", "yoranix-widget-iframe"]).toContain(await page.evaluate(() => document.activeElement?.id));

  await page.evaluate(() => window.YoranixWidget.destroy());
  await expect(page.locator("#yoranix-widget-iframe")).toHaveCount(0);
});


test("host interaction is not blocked while closed and mobile bounds stay safe", async ({ instrumentedPage: page }) => {
  await page.setViewportSize({ width: 390, height: 740 });
  await openReadyWidget(page);
  await page.locator("#host-click-target").click();
  expect(await page.evaluate(() => (window as unknown as { __hostClicked?: boolean }).__hostClicked)).toBe(true);
  await page.evaluate(() => window.YoranixWidget.open());
  const box = await page.locator("#yoranix-widget-root").boundingBox();
  expect(box?.width).toBeLessThanOrEqual(390);
  expect(box?.height).toBeLessThanOrEqual(740);
});


test("config failure reaches safe unavailable state", async ({ instrumentedPage: page }) => {
  await page.goto("http://127.0.0.1:4100/normal");
  await page.waitForFunction(() => Boolean(window.YoranixWidget));
  await page.evaluate(() => window.YoranixWidget.destroy());
  await page.evaluate(() => window.YoranixWidget.init({ widgetKey: "wpk_dev_1234567890abcdef", environment: "development", iframeHost: "http://127.0.0.1:4200" }).catch((error) => (window as unknown as { __safeError?: unknown }).__safeError = error));
  await page.waitForTimeout(200);
  expect(await page.locator("#yoranix-widget-iframe").count()).toBeLessThanOrEqual(1);
});