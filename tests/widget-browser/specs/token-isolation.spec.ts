import { test, expect, openReadyWidget, sendHarnessMessage, parentPostMessages, consoleMessages, SESSION_TOKEN } from "../helpers/fixtures";

test("session token remains isolated from host page and postMessage", async ({ instrumentedPage: page, servers }) => {
  const frame = await openReadyWidget(page);
  await sendHarnessMessage(frame, "Token isolation check");

  const hostSnapshot = await page.evaluate(() => ({
    globals: Object.keys(window).filter((key) => key.toLowerCase().includes("yoranix")),
    api: JSON.stringify(window.YoranixWidget),
    html: document.documentElement.outerHTML,
    localStorage: JSON.stringify({ ...localStorage }),
    sessionStorage: JSON.stringify({ ...sessionStorage }),
    cookies: document.cookie,
    iframeSrc: document.querySelector("iframe")?.getAttribute("src") ?? "",
  }));
  expect(JSON.stringify(hostSnapshot)).not.toContain(SESSION_TOKEN);
  expect(hostSnapshot.iframeSrc).not.toContain("pss_");

  const postMessages = await parentPostMessages(page);
  expect(postMessages.every((entry) => entry.targetOrigin !== "*")).toBe(true);
  expect(JSON.stringify(postMessages)).not.toContain(SESSION_TOKEN);
  expect(JSON.stringify(postMessages)).not.toContain("Token isolation check");
  expect(JSON.stringify(consoleMessages(page))).not.toContain(SESSION_TOKEN);

  const configRequest = servers.apiRequests.find((request) => request.url.endsWith("/config"));
  const sessionRequest = servers.apiRequests.find((request) => request.url.endsWith("/sessions"));
  const messageRequest = servers.apiRequests.find((request) => request.url.endsWith("/messages"));
  expect(configRequest?.body ?? "").not.toContain(SESSION_TOKEN);
  expect(sessionRequest?.body ?? "").not.toContain(SESSION_TOKEN);
  expect(messageRequest?.body).toContain(SESSION_TOKEN);
});


test("host page cannot read iframe storage or obtain token through SDK events", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page);
  await sendHarnessMessage(frame, "Host isolation check");
  const accessResult = await page.evaluate(() => {
    const iframe = document.querySelector("iframe") as HTMLIFrameElement | null;
    try {
      return iframe?.contentWindow?.sessionStorage.getItem("anything") ?? "readable";
    } catch (error) {
      return (error as Error).name;
    }
  });
  expect(accessResult).toMatch(/SecurityError|Denied|Permission/i);
  const events = await page.evaluate(() => JSON.stringify((window as unknown as { __widgetEvents?: unknown }).__widgetEvents ?? []));
  expect(events).not.toContain(SESSION_TOKEN);
});