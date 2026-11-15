import { expect, test } from "@playwright/test";
import { ADMIN_STATE } from "./helpers";

// Visuelle Regressionstests: fangen ungewollte Änderungen am Erscheinungsbild ab (z. B. durch Updates).
// Neue Referenzbilder: siehe e2e/README.md (--update-snapshots im Playwright-Container).
const viewports = { desktop: { width: 1280, height: 900 }, handy: { width: 390, height: 844 } };

for (const scheme of ["light", "dark"] as const) {
  for (const [device, viewport] of Object.entries(viewports)) {
    const name = `${device}-${scheme === "light" ? "hell" : "dunkel"}`;
    test.describe(name, () => {
      test.use({ colorScheme: scheme, viewport });

      test("Anmeldeseite", async ({ page }) => {
        await page.goto("/anmeldung/login/");
        await page.evaluate(() => document.fonts.ready);
        await expect(page).toHaveScreenshot(`anmeldung-${name}.png`, { fullPage: true });
      });

      test("Startseite", async ({ browser }) => {
        const context = await browser.newContext({ storageState: ADMIN_STATE, colorScheme: scheme, viewport });
        const page = await context.newPage();
        await page.goto("/");
        await page.evaluate(() => document.fonts.ready);
        await expect(page).toHaveScreenshot(`start-${name}.png`, { fullPage: true });
        await context.close();
      });

      test("Bausteine", async ({ browser }) => {
        const context = await browser.newContext({ storageState: ADMIN_STATE, colorScheme: scheme, viewport });
        const page = await context.newPage();
        await page.goto("/bausteine/");
        await page.evaluate(() => document.fonts.ready);
        await expect(page).toHaveScreenshot(`bausteine-${name}.png`, { fullPage: true });
        await context.close();
      });
    });
  }
}
