import { test, expect, openReadyWidget, parentPostMessages, WIDGET_ORIGIN } from "../helpers/fixtures";

test("postMessage uses exact origins and ignores forged host messages", async ({ instrumentedPage: page }) => {
  await openReadyWidget(page);
  const before = await page.locator("#yoranix-widget-root").getAttribute("data-yoranix-state");
  await page.evaluate(() => {
    window.postMessage({ protocol: "yoranix-widget", version: 1, messageId: "fake", type: "widget_state_changed", source: "yoranix-iframe", payload: { state: "ready_open" }, sentAt: new Date().toISOString() }, window.location.origin);
  });
  await page.waitForTimeout(100);
  await expect(page.locator("#yoranix-widget-root")).toHaveAttribute("data-yoranix-state", before ?? "closed");

  const messages = await parentPostMessages(page);
  expect(messages.length).toBeGreaterThan(0);
  expect(messages.every((entry) => entry.targetOrigin !== "*")).toBe(true);
});


test("malformed iframe lifecycle messages are ignored safely", async ({ instrumentedPage: page, browserName }) => {
  test.skip(browserName === "firefox", "Firefox does not allow constructing MessageEvent.source with cross-origin WindowProxy in this synthetic-hostility check.");
  await openReadyWidget(page);
  const boxBefore = await page.locator("#yoranix-widget-root").boundingBox();
  await page.evaluate((origin) => {
    const iframe = document.querySelector("iframe") as HTMLIFrameElement;
    window.dispatchEvent(new MessageEvent("message", {
      origin,
      source: iframe.contentWindow,
      data: { protocol: "wrong", version: 999, messageId: "bad", type: "resize_request", source: "yoranix-iframe", payload: { width: 999999, height: -1 }, sentAt: new Date().toISOString() },
    }));
  }, WIDGET_ORIGIN);
  await page.waitForTimeout(100);
  const boxAfter = await page.locator("#yoranix-widget-root").boundingBox();
  expect(boxAfter?.width).toBe(boxBefore?.width);
  expect(boxAfter?.height).toBe(boxBefore?.height);
});