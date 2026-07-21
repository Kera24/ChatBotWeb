import { test as base, expect, type Page, type Frame } from "@playwright/test";
import { startWidgetBrowserServers, SESSION_TOKEN, HOST_ORIGIN, WIDGET_ORIGIN, API_ORIGIN } from "../servers/test-servers";

type Fixtures = {
  servers: Awaited<ReturnType<typeof startWidgetBrowserServers>>;
  instrumentedPage: Page;
};

export const test = base.extend<Fixtures>({
  servers: [async ({}, use) => {
    const servers = await startWidgetBrowserServers();
    await use(servers);
    await servers.close();
  }, { scope: "test" }],
  instrumentedPage: async ({ page, servers: _servers }, use) => {
    const consoleMessages: string[] = [];
    page.on("console", (message) => consoleMessages.push(message.text()));
    await page.addInitScript(() => {
      const original = window.postMessage;
      Object.defineProperty(window, "__yoranixPostMessages", { value: [], configurable: true });
      window.postMessage = function patchedPostMessage(message: unknown, targetOrigin: string, transfer?: Transferable[]) {
        try {
          (window as unknown as { __yoranixPostMessages: Array<{ targetOrigin: string; text: string }> }).__yoranixPostMessages.push({
            targetOrigin: String(targetOrigin),
            text: JSON.stringify(message),
          });
        } catch {
          // Test instrumentation must not alter runtime behavior.
        }
        return original.call(window, message, targetOrigin, transfer as never);
      } as typeof window.postMessage;
    });
    (page as Page & { __consoleMessages?: string[] }).__consoleMessages = consoleMessages;
    await use(page);
  },
});

export { expect, SESSION_TOKEN, HOST_ORIGIN, WIDGET_ORIGIN, API_ORIGIN };

export async function openReadyWidget(page: Page, path = "/normal"): Promise<Frame> {
  await page.goto(`${HOST_ORIGIN}${path}`);
  try {
    await page.waitForFunction(() => Boolean(window.YoranixWidget?.isReady?.()));
  } catch (error) {
    const debugState = await page.evaluate(() => ({
      hasGlobal: Boolean(window.YoranixWidget),
      state: window.YoranixWidget?.getState?.(),
      initError: (() => { const err = (window as unknown as { __initError?: { code?: string; message?: string; phase?: string } }).__initError; return err ? { code: err.code, message: err.message, phase: err.phase } : null; })(),
      iframeCount: document.querySelectorAll("iframe").length,
      html: document.body.innerHTML,
    }));
    throw new Error(`Widget did not become ready: ${JSON.stringify(debugState)}`, { cause: error });
  }
  const frame = page.frames().find((entry) => entry.url().startsWith(`${WIDGET_ORIGIN}/embed/`));
  expect(frame, "widget iframe frame").toBeTruthy();
  await frame!.waitForFunction(() => Boolean((window as unknown as { __yoranixWidgetTestHarness?: unknown }).__yoranixWidgetTestHarness));
  return frame!;
}

export async function sendHarnessMessage(frame: Frame, message = "Hello from browser test") {
  return frame.evaluate(async (text) => {
    const harness = (window as unknown as { __yoranixWidgetTestHarness: { sendMessage(message: string): Promise<unknown> } }).__yoranixWidgetTestHarness;
    return harness.sendMessage(text);
  }, message);
}

export async function getHarnessState(frame: Frame) {
  return frame.evaluate(() => {
    const harness = (window as unknown as { __yoranixWidgetTestHarness: { state(): unknown } }).__yoranixWidgetTestHarness;
    return harness.state();
  });
}

export async function getHarnessConversation(frame: Frame) {
  return frame.evaluate(() => {
    const harness = (window as unknown as { __yoranixWidgetTestHarness: { conversation(): unknown } }).__yoranixWidgetTestHarness;
    return harness.conversation();
  });
}
export async function parentPostMessages(page: Page) {
  return page.evaluate(() => (window as unknown as { __yoranixPostMessages?: Array<{ targetOrigin: string; text: string }> }).__yoranixPostMessages ?? []);
}

export function consoleMessages(page: Page): string[] {
  return ((page as Page & { __consoleMessages?: string[] }).__consoleMessages ?? []);
}