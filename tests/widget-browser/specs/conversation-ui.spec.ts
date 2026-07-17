import { test, expect, openReadyWidget, getHarnessConversation, SESSION_TOKEN } from "../helpers/fixtures";

test("welcome suggestions send through iframe-owned API and render answered conversation", async ({ instrumentedPage: page, servers }) => {
  const frame = await openReadyWidget(page);
  await page.evaluate(() => window.YoranixWidget.open());
  await expect(frame.getByRole("heading", { name: "Ask Yoranix" })).toBeVisible();
  await expect(frame.getByRole("button", { name: /What can you do/ })).toBeVisible();

  await frame.getByRole("button", { name: /What can you do/ }).click();
  await expect(frame.getByLabel("You said")).toContainText("What can you do?");
  await expect(frame.getByText("Safe answer")).toBeVisible();

  expect(servers.apiRequests.filter((request) => request.url.endsWith("/sessions"))).toHaveLength(1);
  expect(servers.apiRequests.filter((request) => request.url.endsWith("/messages"))).toHaveLength(1);
  const conversation = JSON.stringify(await getHarnessConversation(frame));
  expect(conversation).not.toContain(SESSION_TOKEN);
  expect(conversation).not.toContain("wid_");
});

test("double clicking a suggestion creates one logical message request", async ({ instrumentedPage: page, servers }) => {
  const frame = await openReadyWidget(page, "/slow");
  await page.evaluate(() => window.YoranixWidget.open());
  const button = frame.getByRole("button", { name: /What can you do/ });
  await button.evaluate((element) => { (element as HTMLButtonElement).click(); (element as HTMLButtonElement).click(); });
  await expect(frame.getByText("Safe answer")).toBeVisible();
  expect(servers.apiRequests.filter((request) => request.url.endsWith("/messages"))).toHaveLength(1);
});

test("fallback response uses a visible non-colour-only label", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page, "/fallback");
  await page.evaluate(() => window.YoranixWidget.open());
  await frame.getByRole("button", { name: /What can you do/ }).click();
  await expect(frame.getByText("Fallback answer", { exact: true })).toBeVisible();
  await expect(frame.getByText("I could not find this in the available information.")).toBeVisible();
});

test("low-confidence response uses a visible non-colour-only label", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page, "/low-confidence");
  await page.evaluate(() => window.YoranixWidget.open());
  await frame.getByRole("button", { name: /What can you do/ }).click();
  await expect(frame.getByText("Low confidence", { exact: true })).toBeVisible();
  await expect(frame.getByText(/please verify/i)).toBeVisible();
});

test("malicious answer text remains inert in the message presentation", async ({ instrumentedPage: page }) => {
  const frame = await openReadyWidget(page, "/malicious");
  await page.evaluate(() => window.YoranixWidget.open());
  await frame.getByRole("button", { name: /What can you do/ }).click();
  await expect(frame.getByText("<script>alert(1)</script>")).toBeVisible();
  expect(await frame.locator("main script").count()).toBe(0);
  expect(await frame.locator("main img").count()).toBe(0);
  expect(await frame.locator("main a").count()).toBe(0);
});

test("close and reopen preserves in-memory conversation while iframe reload starts fresh", async ({ instrumentedPage: page }) => {
  let frame = await openReadyWidget(page);
  await page.evaluate(() => window.YoranixWidget.open());
  await frame.getByRole("button", { name: /What can you do/ }).click();
  await expect(frame.getByText("Safe answer")).toBeVisible();
  await page.evaluate(() => window.YoranixWidget.close());
  await page.evaluate(() => window.YoranixWidget.open());
  await expect(frame.getByText("Safe answer")).toBeVisible();

  await page.reload();
  frame = await openReadyWidget(page);
  await page.evaluate(() => window.YoranixWidget.open());
  await expect(frame.getByRole("heading", { name: "Ask Yoranix" })).toBeVisible();
  await expect(frame.getByText("Safe answer")).toHaveCount(0);
});
