import { expect, test, type Browser, type BrowserContextOptions, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { ADMIN_STATE, freshNotificationPermission, loginWithPassword } from "./helpers";

/**
 * Screenshots für die Hilfe im Portal (ADR 0016). Läuft als eigenes Projekt nach allen anderen Tests und nutzt deren
 * Daten (Mitglieder, Trainerin Clara, Übungsleiterin Dora, Eltern mit zwei Kindern).
 * Mit HELP_SCREENSHOTS=1 (`npm run help:screenshots`) landen die Bilder in portal/help/static/help/img, sonst nur in
 * test-results – die CI prüft damit die Abläufe, ohne Bilder zu vergleichen (Datumswerte ändern sich täglich).
 */
const OUT = process.env.HELP_SCREENSHOTS ? "portal/help/static/help/img" : "test-results/hilfe";
mkdirSync(OUT, { recursive: true });

const VIEWS: Record<string, BrowserContextOptions> = {
  desktop: { viewport: { width: 1280, height: 800 } },
  handy: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};

type State = string | Awaited<ReturnType<import("@playwright/test").BrowserContext["storageState"]>> | undefined;

async function stateFor(browser: Browser, email: string, password: string): Promise<State> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await loginWithPassword(page, email, password);
  const state = await context.storageState();
  await context.close();
  return state;
}

/** Je ein Bild für Desktop und Handy. ``open`` führt zur Seite, ``target`` wählt optional einen Ausschnitt. */
async function shoot(
  browser: Browser,
  state: State,
  name: string,
  open: (page: Page) => Promise<void>,
  target?: (page: Page) => import("@playwright/test").Locator,
) {
  for (const [view, options] of Object.entries(VIEWS)) {
    const context = await browser.newContext({ ...options, storageState: state, colorScheme: "light", locale: "de-DE" });
    await freshNotificationPermission(context);
    const page = await context.newPage();
    await open(page);
    await page.evaluate(() => document.fonts.ready);
    const path = `${OUT}/${name}-${view}.jpg`;
    if (target) {
      await target(page).screenshot({ path, type: "jpeg", quality: 80, animations: "disabled" });
    } else {
      await page.screenshot({ path, type: "jpeg", quality: 80, animations: "disabled" });
    }
    await context.close();
  }
}

function lastMonthPath(): string {
  const now = new Date();
  const month = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return `/abrechnung/${month.getFullYear()}/${month.getMonth() + 1}/`;
}

test("Screenshots für die Hilfe", async ({ browser }) => {
  test.setTimeout(180_000);
  const parents = await stateFor(browser, "eltern-zwei@test.local", "Sicher-Eltern-321");
  const clara = await stateFor(browser, "clara@test.local", "Sicher-Trainer-789");
  const dora = await stateFor(browser, "dora@test.local", "Sicher-Trainer-246");

  await shoot(browser, undefined, "login", async (page) => {
    await page.goto("/anmeldung/login/");
    await expect(page.getByRole("button", { name: "Mit Passkey anmelden" })).toBeVisible();
  });

  // Eltern mit zwei Kindern
  await shoot(browser, parents, "termine", async (page) => {
    await page.goto("/termine/");
    await expect(page.getByRole("heading", { level: 1, name: "Termine" })).toBeVisible();
  });
  await shoot(browser, parents, "anmelden", async (page) => {
    await page.goto("/termine/");
    const href = await page.locator('a[href*="/anmelden/"]').first().getAttribute("href");
    expect(href).toBeTruthy();
    await page.goto(href!);
    await expect(page.getByRole("button", { name: "Anmelden" })).toBeVisible();
  });
  await shoot(browser, parents, "meine-daten", async (page) => {
    await page.goto("/meine-daten/");
    await page.getByRole("link", { name: /David Dachs/ }).click();
    await expect(page.getByRole("link", { name: "Bearbeiten" })).toBeVisible();
  });
  await shoot(browser, parents, "zugang", async (page) => {
    await page.goto("/zugang/anmeldung/");
    await expect(page.getByRole("heading", { level: 1, name: "Meine Anmeldung" })).toBeVisible();
  });
  await shoot(
    browser,
    parents,
    "benachrichtigungen",
    async (page) => {
      await page.goto("/zugang/anmeldung/");
      await expect(page.getByRole("button", { name: "Push-Benachrichtigungen auf diesem Gerät einschalten" })).toBeVisible();
    },
    (page) => page.getByRole("region", { name: "Benachrichtigungen" }),
  );

  // Trainerin
  await shoot(browser, clara, "stunden", async (page) => {
    await page.goto("/stunden/");
    await expect(page.getByRole("heading", { level: 1, name: "Meine Stunden" })).toBeVisible();
  });
  await shoot(browser, clara, "termin-team", async (page) => {
    await page.goto("/stunden/");
    await page.getByRole("region", { name: "Kommende" }).getByRole("link", { name: "Randori-Lehrgang" }).click();
    await expect(page.getByRole("heading", { name: /Teilnehmer/ })).toBeVisible();
  });
  await shoot(browser, clara, "nicht-dabei", async (page) => {
    await page.goto("/stunden/");
    const href = await page.getByRole("region", { name: "Vergangen" }).getByRole("link", { name: "Randori-Lehrgang" }).first().getAttribute("href");
    await page.goto(`${href}nicht-dabei/`);
    await page.getByLabel("Ich wurde vertreten").check();
    await expect(page.getByLabel("Vertreten von")).toBeVisible();
  });
  await shoot(browser, dora, "abrechnung-monat", async (page) => {
    await page.goto(lastMonthPath());
    await expect(page.getByRole("heading", { name: "Bestätigte Stunden" })).toBeVisible();
  });

  // Abteilungsleitung
  await shoot(browser, ADMIN_STATE, "mitglieder", async (page) => {
    await page.goto("/mitglieder/");
    await expect(page.getByRole("heading", { level: 1, name: "Mitglieder" })).toBeVisible();
  });
  await shoot(browser, ADMIN_STATE, "mitglied", async (page) => {
    await page.goto("/mitglieder/");
    await page.getByRole("link", { name: "Clever, Clara" }).click();
    await expect(page.getByRole("heading", { name: "Zugänge" })).toBeVisible();
  });
  await shoot(browser, ADMIN_STATE, "veranstaltung-anlegen", async (page) => {
    await page.goto("/veranstaltungen/neu/");
    await page.getByLabel("Titel").fill("Sommertraining");
    await page.getByLabel("Wiederkehrend").check();
  });
  await shoot(browser, ADMIN_STATE, "abrechnungen", async (page) => {
    await page.goto("/abrechnung/alle/");
    await expect(page.getByRole("heading", { level: 1, name: "Abrechnungen" })).toBeVisible();
  });
  await shoot(browser, ADMIN_STATE, "protokoll", async (page) => {
    await page.goto("/protokoll/");
    await expect(page.getByRole("heading", { level: 1, name: "Protokoll" })).toBeVisible();
  });
});
