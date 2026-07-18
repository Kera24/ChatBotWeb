import { test, expect, openReadyWidget } from "../helpers/fixtures";

async function openWidgetForVisual(page: Parameters<typeof openReadyWidget>[0], path = "/normal") {
  const frame = await openReadyWidget(page, path);
  await page.evaluate(() => window.YoranixWidget.open());
  await frame.addStyleTag({ content: `
    *, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }
    .yw-live-region { visibility: hidden !important; }
  ` });
  return frame;
}

async function screenshotWidget(page: Parameters<typeof openReadyWidget>[0], name: string) {
  await expect(page.locator("#yoranix-widget-root")).toHaveScreenshot(name, {
    animations: "disabled",
    caret: "hide",
    maxDiffPixelRatio: 0.02,
  });
}

test("launcher closed desktop", async ({ instrumentedPage: page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openReadyWidget(page);
  await screenshotWidget(page, "launcher-closed-desktop.png");
});

test("welcome desktop", async ({ instrumentedPage: page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openWidgetForVisual(page);
  await screenshotWidget(page, "welcome-desktop.png");
});

test("active conversation with citations desktop", async ({ instrumentedPage: page }) => {
  const frame = await openWidgetForVisual(page, "/citations");
  await frame.getByRole("textbox", { name: "Message" }).fill("Show cited answer");
  await frame.getByRole("textbox", { name: "Message" }).press("Enter");
  await expect(frame.getByText("Safe cited answer")).toBeVisible();
  await frame.getByText("Sources (1)").click();
  await screenshotWidget(page, "conversation-citations-desktop.png");
});

test("fallback and low confidence states", async ({ instrumentedPage: page }) => {
  let frame = await openWidgetForVisual(page, "/fallback");
  await frame.getByRole("textbox", { name: "Message" }).fill("Unknown answer");
  await frame.getByRole("textbox", { name: "Message" }).press("Enter");
  await expect(frame.getByText("Fallback answer", { exact: true })).toBeVisible();
  await screenshotWidget(page, "fallback-desktop.png");

  await page.evaluate(() => window.YoranixWidget.destroy());
  frame = await openWidgetForVisual(page, "/low-confidence");
  await frame.getByRole("textbox", { name: "Message" }).fill("Maybe answer");
  await frame.getByRole("textbox", { name: "Message" }).press("Enter");
  await expect(frame.getByText("Low confidence", { exact: true })).toBeVisible();
  await screenshotWidget(page, "low-confidence-desktop.png");
});

test("mobile welcome and conversation", async ({ instrumentedPage: page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const frame = await openWidgetForVisual(page, "/citations");
  await screenshotWidget(page, "mobile-welcome.png");
  await frame.getByRole("textbox", { name: "Message" }).fill("Mobile cited answer");
  await frame.getByRole("textbox", { name: "Message" }).press("Enter");
  await expect(frame.getByText("Safe cited answer")).toBeVisible();
  await frame.getByText("Sources (1)").click();
  await screenshotWidget(page, "mobile-conversation-citations.png");
});

