import { expect, test } from "@playwright/test";
import { ADMIN_STATE, expectNoA11yViolations } from "./helpers";

const pages = [
  { path: "/", heading: /^Hallo/ },
  { path: "/verwaltung/benutzer/", heading: "Benutzer" },
  { path: "/zugang/anmeldung/", heading: "Meine Anmeldung" },
  { path: "/bausteine/", heading: "Bausteine" },
];

for (const scheme of ["light", "dark"] as const) {
  test.describe(`Barrierefreiheit (${scheme === "light" ? "hell" : "dunkel"})`, () => {
    test.use({ colorScheme: scheme });

    test("Anmeldeseite", async ({ page }) => {
      await page.goto("/anmeldung/login/");
      await expectNoA11yViolations(page);
    });

    for (const { path, heading } of pages) {
      test(`Seite ${path}`, async ({ browser }) => {
        const context = await browser.newContext({ storageState: ADMIN_STATE, colorScheme: scheme });
        const page = await context.newPage();
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
        await expectNoA11yViolations(page);
        await context.close();
      });
    }
  });
}

test("Umschalter zwischen hellem und dunklem Design merkt sich die Wahl", async ({ page }) => {
  await page.goto("/anmeldung/login/");
  await expect(page.locator("html")).toHaveAttribute("data-bs-theme", "light");
  await page.getByRole("button", { name: "Dunkles Design einschalten" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-bs-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-bs-theme", "dark");
});

test("Portal ist als App installierbar (Manifest und Service Worker)", async ({ page, request }) => {
  const manifest = await (await request.get("/manifest.webmanifest")).json();
  expect(manifest.name).toBe("Wedeler TSV Judo");
  expect(manifest.display).toBe("standalone");
  await page.goto("/anmeldung/login/");
  const registered = await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
    return (await navigator.serviceWorker.getRegistrations()).length;
  });
  expect(registered).toBe(1);
});
