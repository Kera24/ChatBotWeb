import { test, expect, openReadyWidget } from "../helpers/fixtures";

test("iframe shell exposes accessible status semantics", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page);
  const shell = frame.locator("#app");
  await expect(shell).toHaveAttribute("role", "status");
  await expect(shell).toHaveAttribute("aria-live", "polite");
  await expect(shell).toContainText("Widget ready");
  await expect(page.locator("#yoranix-widget-iframe")).toHaveAttribute("title", "Yoranix chat widget");
});


test("console output does not leak public secrets or content", async ({ instrumentedPage: page }) => {
  const consoleMessages: string[] = [];
  page.on("console", (message) => consoleMessages.push(message.text()));
  const frame = await openReadyWidget(page);
  await frame.evaluate(async () => {
    const harness = (window as unknown as { __yoranixWidgetTestHarness: { sendMessage(message: string): Promise<unknown> } }).__yoranixWidgetTestHarness;
    await harness.sendMessage("Do not log this user message");
  });
  const joined = consoleMessages.join("\n");
  expect(joined).not.toContain("pss_dev_");
  expect(joined).not.toContain("Do not log this user message");
  expect(joined).not.toContain("Safe answer");
});