import { test, expect, openReadyWidget, consoleMessages, parentPostMessages, SESSION_TOKEN } from "../helpers/fixtures";

async function assertNoHorizontalOverflow(frame: Awaited<ReturnType<typeof openReadyWidget>>) {
  const overflow = await frame.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1 || document.body.scrollWidth > document.body.clientWidth + 1);
  expect(overflow).toBe(false);
}

test("responsive breakpoints keep controls visible and bounded", async ({ instrumentedPage: page }) => {
  for (const size of [
    { width: 1920, height: 1080 },
    { width: 1440, height: 900 },
    { width: 1280, height: 720 },
    { width: 1024, height: 768 },
    { width: 390, height: 844 },
    { width: 320, height: 568 },
    { width: 667, height: 375 },
  ]) {
    await page.setViewportSize(size);
    const frame = await openReadyWidget(page);
    await page.evaluate(() => window.YoranixWidget.open());
    const box = await page.locator("#yoranix-widget-root").boundingBox();
    expect(box?.width ?? 0).toBeLessThanOrEqual(size.width);
    expect(box?.height ?? 0).toBeLessThanOrEqual(size.height);
    await expect(frame.getByRole("dialog", { name: "Yoranix" }).getByLabel("Close chat")).toBeVisible();
    await expect(frame.getByRole("textbox", { name: "Message" })).toBeVisible();
    await assertNoHorizontalOverflow(frame);
    await page.evaluate(() => window.YoranixWidget.destroy());
  }
});

test("long text, citations, and privacy content wrap without leaking to parent", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page, "/citations");
  await page.evaluate(() => window.YoranixWidget.open());
  await frame.getByRole("textbox", { name: "Message" }).fill("A".repeat(260));
  await frame.getByRole("textbox", { name: "Message" }).press("Enter");
  await expect(frame.getByText("Safe cited answer")).toBeVisible();
  await frame.getByText("Sources (1)").click();
  await assertNoHorizontalOverflow(frame);
  const parentMessages = JSON.stringify(await parentPostMessages(page));
  expect(parentMessages).not.toContain("Safe cited answer");
  expect(parentMessages).not.toContain("Public guide");
  expect(parentMessages).not.toContain("A".repeat(80));
});

test("keyboard focus stays within the open iframe panel and Escape closes", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page);
  await page.evaluate(() => window.YoranixWidget.open());
  await frame.getByRole("heading", { name: "Yoranix", exact: true }).focus();
  for (let index = 0; index < 8; index += 1) await frame.page().keyboard.press("Tab");
  const activeInside = await frame.evaluate(() => Boolean(document.activeElement && document.querySelector(".yw-panel")?.contains(document.activeElement)));
  expect(activeInside).toBe(true);
  await frame.page().keyboard.press("Escape");
  await expect(page.locator("#yoranix-widget-root")).toHaveAttribute("data-yoranix-state", "closed");
});

test("reduced motion and forced-colours compatible semantics remain present", async ({ instrumentedPage: page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "dark" });
  const frame = await openReadyWidget(page, "/dark");
  await page.evaluate(() => window.YoranixWidget.open());
  await expect(frame.getByRole("dialog", { name: "Yoranix" })).toBeVisible();
  const preparingAnimation = await frame.locator(".yw-preparing__line").evaluateAll((nodes) => nodes.length === 0 ? "none" : getComputedStyle(nodes[0]).animationName);
  expect(["none", ""]).toContain(preparingAnimation);
  expect(JSON.stringify(consoleMessages(page))).not.toContain(SESSION_TOKEN);
});

test("release accessibility smoke covers active, validation, citations, and recovery states", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page, "/citations");
  await page.evaluate(() => window.YoranixWidget.open());
  await expect(frame.getByRole("dialog", { name: "Yoranix" })).toBeVisible();
  await frame.getByRole("textbox", { name: "Message" }).fill("   ");
  await frame.getByRole("textbox", { name: "Message" }).press("Enter");
  await expect(frame.getByRole("textbox", { name: "Message" })).toHaveAttribute("aria-invalid", "true");
  await frame.getByRole("textbox", { name: "Message" }).fill("Show sources");
  await frame.getByRole("textbox", { name: "Message" }).press("Enter");
  await expect(frame.getByText("Sources (1)")).toBeVisible();
  await expect(frame.locator("[aria-live='polite']").first()).toBeAttached();
  expect(consoleMessages(page).join("\n")).not.toMatch(/session|token|idempotency/i);
});
