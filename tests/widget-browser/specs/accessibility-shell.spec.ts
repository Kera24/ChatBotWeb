import { test, expect, openReadyWidget } from "../helpers/fixtures";

test("iframe shell exposes accessible structural semantics", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page);
  const shell = frame.locator("#app");
  await expect(shell).toHaveAttribute("data-widget-state", "closed");
  await expect(frame.getByRole("button", { name: "Chat" })).toBeVisible();
  await page.evaluate(() => window.YoranixWidget.open());
  await expect(frame.getByRole("dialog", { name: "Yoranix" })).toBeVisible();
  await expect(frame.getByRole("heading", { name: "Yoranix", exact: true })).toBeVisible();
  await expect(frame.getByText("AI assistant", { exact: true })).toBeVisible();
  await expect(frame.getByRole("region", { name: "Chat conversation" })).toBeVisible();
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
