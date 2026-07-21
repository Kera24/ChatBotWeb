import { test, expect, openReadyWidget, HOST_ORIGIN } from "../helpers/fixtures";

test("shell applies dark configuration tokens", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page, "/dark");
  await page.evaluate(() => window.YoranixWidget.open());
  await expect(frame.locator("#app")).toHaveAttribute("data-widget-state", "open");
  await expect.poll(() => frame.locator("#app").evaluate((node) => getComputedStyle(node).getPropertyValue("--yw-color-scheme").trim())).toBe("dark");
  await expect(frame.getByRole("dialog", { name: "Yoranix" })).toBeVisible();
});

test("invalid customer colour response fails safely before rendering", async ({ instrumentedPage: page }) => {
  await page.goto(`${HOST_ORIGIN}/invalid-colour`);
  await page.waitForFunction(() => Boolean(window.YoranixWidget));
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => window.YoranixWidget.getState())).toBe("failed");
  const initError = await page.evaluate(() => {
    const error = (window as unknown as { __initError?: { code?: string; message?: string } }).__initError;
    return error ? { code: error.code, message: error.message } : null;
  });
  expect(initError?.code).toBeTruthy();
});

test("panel remains viewport bounded on desktop and mobile", async ({ instrumentedPage: page }) => {
  await openReadyWidget(page);
  await page.evaluate(() => window.YoranixWidget.open());
  const desktopBox = await page.locator("#yoranix-widget-root").boundingBox();
  expect(desktopBox?.width).toBeLessThanOrEqual(420);
  expect(desktopBox?.height).toBeLessThanOrEqual(680);

  await page.goto(`${HOST_ORIGIN}/normal`);
  await page.setViewportSize({ width: 375, height: 667 });
  await openReadyWidget(page);
  await page.evaluate(() => window.YoranixWidget.open());
  const mobileBox = await page.locator("#yoranix-widget-root").boundingBox();
  expect(mobileBox?.width).toBeLessThanOrEqual(375);
  expect(mobileBox?.height).toBeLessThanOrEqual(667);
});

