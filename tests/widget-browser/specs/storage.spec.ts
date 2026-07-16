import { test, expect, openReadyWidget, sendHarnessMessage, SESSION_TOKEN } from "../helpers/fixtures";

test("config cache uses ETag and session restores after iframe reload in same tab", async ({ instrumentedPage: page, servers, browserName }) => {
  const frame = await openReadyWidget(page);
  await sendHarnessMessage(frame, "First send");
  expect(servers.apiRequests.filter((request) => request.url.endsWith("/sessions"))).toHaveLength(1);

  await page.reload();
  await page.waitForFunction(() => Boolean(window.YoranixWidget?.isReady?.()));
  const secondFrame = page.frames().find((entry) => entry.url().includes("/embed/"));
  expect(secondFrame).toBeTruthy();
  await secondFrame!.waitForFunction(() => Boolean((window as unknown as { __yoranixWidgetTestHarness?: unknown }).__yoranixWidgetTestHarness));
  await sendHarnessMessage(secondFrame!, "Second send");

  const configRequests = servers.apiRequests.filter((request) => request.url.endsWith("/config"));
  expect(configRequests.length).toBeGreaterThanOrEqual(2);
  if (browserName !== "webkit") {
    expect(configRequests[1]?.headers["if-none-match"]).toBe('"cfg-1"');
  }
  expect(servers.apiRequests.filter((request) => request.url.endsWith("/sessions"))).toHaveLength(1);
});


test("host origin storage does not contain config cache or session token", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page);
  await sendHarnessMessage(frame, "Storage check");
  const hostStorage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, cookies: document.cookie }));
  expect(JSON.stringify(hostStorage)).not.toContain(SESSION_TOKEN);
  expect(JSON.stringify(hostStorage)).not.toContain("yoranix:widget-session");
});