import { test, expect, openReadyWidget } from "../helpers/fixtures";

test("browser sends Origin and uses route-scoped CORS without cookies", async ({ instrumentedPage: page, servers }) => {
  const frame = await openReadyWidget(page);
  await frame.evaluate(async () => {
    const harness = (window as unknown as { __yoranixWidgetTestHarness: { sendMessage(message: string): Promise<unknown> } }).__yoranixWidgetTestHarness;
    await harness.sendMessage("CORS check");
  });
  for (const request of servers.apiRequests) {
    expect(request.origin).toBe("http://127.0.0.1:4200");
    expect(request.headers.cookie).toBeUndefined();
  }
  const message = servers.apiRequests.find((request) => request.url.endsWith("/messages"));
  expect(message?.headers["idempotency-key"]).toBeTruthy();
});


test("supported CSP permits loader and iframe while blocked frame policy fails safely", async ({ instrumentedPage: page }) => {
  await openReadyWidget(page, "/csp");
  await expect(page.locator("#yoranix-widget-iframe")).toHaveCount(1);

  await page.goto("http://127.0.0.1:4100/blocked-frame");
  await page.waitForTimeout(500);
  expect(await page.evaluate(() => window.YoranixWidget?.isReady?.() ?? false)).toBe(false);
});


test("iframe sandbox and permission attributes stay minimal", async ({ instrumentedPage: page }) => {
  await openReadyWidget(page);
  const attrs = await page.locator("#yoranix-widget-iframe").evaluate((iframe) => ({
    sandbox: iframe.getAttribute("sandbox"),
    allow: iframe.getAttribute("allow"),
    referrerPolicy: iframe.getAttribute("referrerpolicy"),
    title: iframe.getAttribute("title"),
    loading: iframe.getAttribute("loading"),
  }));
  expect(attrs.sandbox).toContain("allow-scripts");
  expect(attrs.sandbox).toContain("allow-same-origin");
  expect(attrs.sandbox).not.toContain("allow-top-navigation");
  expect(attrs.allow ?? "").not.toMatch(/camera|microphone|geolocation|clipboard/i);
  expect(attrs.referrerPolicy).toBe("strict-origin-when-cross-origin");
  expect(attrs.title).toBe("Yoranix chat widget");
  expect(attrs.loading).toBe("lazy");
});