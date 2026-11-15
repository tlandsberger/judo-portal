import { expect, test } from "@playwright/test";
import { expectNoA11yViolations } from "./helpers";

const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36";
const IPHONE_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 19_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/19.0 Mobile/15E148 Safari/604.1";
const mobile = { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true };

test("Android: Hinweis bietet die Installation an und startet den Systemdialog", async ({ browser }) => {
  const context = await browser.newContext({ ...mobile, userAgent: ANDROID_UA });
  const page = await context.newPage();
  await page.goto("/anmeldung/login/");
  // Chrome feuert beforeinstallprompt nur unter echten Bedingungen – hier simuliert.
  await page.evaluate(() => {
    const event = new Event("beforeinstallprompt", { cancelable: true }) as Event & Record<string, unknown>;
    event.prompt = () => ((window as unknown as Record<string, boolean>).__prompted = true);
    event.userChoice = Promise.resolve({ outcome: "accepted" });
    window.dispatchEvent(event);
  });
  const dialog = page.getByRole("dialog", { name: "WTSV Judo als App" });
  await expect(dialog).toBeVisible();
  await expectNoA11yViolations(page);
  await dialog.getByRole("button", { name: "Als App installieren" }).click();
  expect(await page.evaluate(() => (window as unknown as Record<string, boolean>).__prompted)).toBe(true);
  await expect(dialog).toBeHidden();
  await context.close();
});

test("iPhone: Hinweis zeigt die Anleitung, „Später“ hält ihn fern", async ({ browser }) => {
  const context = await browser.newContext({ ...mobile, userAgent: IPHONE_UA });
  const page = await context.newPage();
  await page.goto("/anmeldung/login/");
  const dialog = page.getByRole("dialog", { name: "WTSV Judo als App" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Zum Home-Bildschirm")).toBeVisible();
  await expectNoA11yViolations(page);
  await dialog.getByRole("button", { name: "Später" }).click();
  await expect(dialog).toBeHidden();
  await page.reload();
  await page.waitForTimeout(2500);
  await expect(dialog).toBeHidden();
  await context.close();
});

test("Desktop: kein Hinweis", async ({ page }) => {
  await page.goto("/anmeldung/login/");
  await page.waitForTimeout(2500);
  await expect(page.getByRole("dialog", { name: "WTSV Judo als App" })).toBeHidden();
});
