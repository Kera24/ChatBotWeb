import { test, expect, openReadyWidget, sendHarnessMessage, getHarnessState, SESSION_TOKEN, WIDGET_ORIGIN } from "../helpers/fixtures";

test("complete embed flow loads config, opens, sends a message, and reuses stored session", async ({ instrumentedPage: page, servers }) => {
  const frame = await openReadyWidget(page);
  expect(await page.locator("#yoranix-widget-iframe").getAttribute("src")).toContain(`${WIDGET_ORIGIN}/embed/`);
  expect(servers.apiRequests.filter((request) => request.url.endsWith("/config"))).toHaveLength(1);
  expect(servers.apiRequests.some((request) => request.url.endsWith("/sessions"))).toBe(false);

  await page.evaluate(() => window.YoranixWidget.open());
  await expect(page.locator("#yoranix-widget-root")).toHaveAttribute("data-yoranix-state", "open");
  expect(servers.apiRequests.some((request) => request.url.endsWith("/sessions"))).toBe(false);

  const response = await sendHarnessMessage(frame);
  expect(response).toMatchObject({ answer: "Safe answer", remaining_messages: 18 });
  const sessionRequests = servers.apiRequests.filter((request) => request.url.endsWith("/sessions"));
  const messageRequests = servers.apiRequests.filter((request) => request.url.endsWith("/messages"));
  expect(sessionRequests).toHaveLength(1);
  expect(messageRequests).toHaveLength(1);
  expect(messageRequests[0]?.headers["idempotency-key"]).toBeTruthy();
  expect(messageRequests[0]?.body).toContain(SESSION_TOKEN);

  await page.evaluate(() => window.YoranixWidget.close());
  await expect(page.locator("#yoranix-widget-root")).toHaveAttribute("data-yoranix-state", "closed");
  await page.evaluate(() => window.YoranixWidget.open());
  await expect(page.locator("#yoranix-widget-root")).toHaveAttribute("data-yoranix-state", "open");

  const state = await getHarnessState(frame) as { session: { remainingMessages: number; status: string } };
  expect(state.session.status).toBe("active");
  expect(state.session.remainingMessages).toBe(18);
});


test("duplicate initialisation creates one iframe and conflicting init is rejected", async ({ instrumentedPage: page }) => {
  await openReadyWidget(page, "/duplicate");
  await expect(page.locator("#yoranix-widget-iframe")).toHaveCount(1);
  await expect.poll(() => page.evaluate(() => window.YoranixWidget.getState())).toBe("ready_closed");
  const conflict = await page.evaluate(async () => {
    try {
      await window.YoranixWidget.init({ widgetKey: "wpk_dev_differentkey0000", environment: "development", iframeHost: "http://127.0.0.1:4200" });
      return null;
    } catch (error) {
      return { code: (error as { code?: string }).code, message: (error as Error).message };
    }
  });
  expect(conflict).toMatchObject({ code: "duplicate_initialisation" });
});