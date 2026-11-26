import { expect, test } from "@playwright/test";
import { ADMIN_STATE, expectNoA11yViolations, freshNotificationPermission } from "./helpers";

const pages = [
  { path: "/", heading: /^Hallo/ },
  { path: "/verwaltung/benutzer/", heading: "Benutzer" },
  { path: "/zugang/anmeldung/", heading: "Meine Anmeldung" },
  { path: "/bausteine/", heading: "Bausteine" },
  { path: "/mitglieder/", heading: "Mitglieder" },
  { path: "/mitglieder/import/", heading: "CSV-Import" },
  { path: "/mitglieder/neu/", heading: "Mitglied anlegen" },
  { path: "/meine-daten/", heading: "Meine Daten" },
  { path: "/mitglieder/interessen/", heading: "Interessen" },
  { path: "/termine/", heading: "Termine" },
  { path: "/trainingstausch/", heading: "Trainingstausch" },
  { path: "/veranstaltungen/", heading: "Veranstaltungen" },
  { path: "/veranstaltungen/neu/", heading: "Veranstaltung anlegen" },
  { path: "/zielgruppen/", heading: "Zielgruppen-Vorlagen" },
  { path: "/zielgruppen/neu/", heading: "Vorlage anlegen" },
  { path: "/rollen/", heading: "Rollen" },
  { path: "/rollen/neu/", heading: "Rolle anlegen" },
  { path: "/veranstaltungsarten/", heading: "Veranstaltungsarten" },
  { path: "/veranstaltungsarten/neu/", heading: "Veranstaltungsart anlegen" },
  { path: "/abrechnung/alle/", heading: "Abrechnungen" },
  { path: "/abrechnung/alle/pruefen/", heading: "Prüfansicht" },
  { path: "/abrechnung/saetze/", heading: "Stundensätze" },
  { path: "/protokoll/", heading: "Protokoll" },
  { path: "/meine-daten/auskunft/", heading: "Datenauskunft (Art. 15 DSGVO)" },
  { path: "/zugang/loeschen/", heading: "Meinen Zugang löschen" },
  { path: "/hilfe/", heading: "Hilfe" },
  { path: "/hilfe/erste-schritte/", heading: "Erste Schritte" },
  { path: "/hilfe/veranstaltungen/", heading: "Veranstaltungen planen" },
  { path: "/uke/", heading: "KI-Assistent Uke" },
  { path: "/hilfe/uke/", heading: "Uke, der Assistent" },
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

test("Push-Benachrichtigungen lassen sich einschalten; die Startseite bietet sie an", async ({ browser }) => {
  const context = await browser.newContext({ storageState: ADMIN_STATE });
  await freshNotificationPermission(context);
  const page = await context.newPage();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Benachrichtigungen aufs Handy?" })).toBeVisible();
  await page.goto("/zugang/anmeldung/");
  const section = page.getByRole("region", { name: "Benachrichtigungen" });
  await expect(section.getByRole("button", { name: "Push-Benachrichtigungen auf diesem Gerät einschalten" })).toBeVisible();
  await expectNoA11yViolations(page);
  // „Nein danke“ auf der Startseite blendet den Hinweis auf diesem Gerät dauerhaft aus
  await page.goto("/");
  await page.getByRole("button", { name: "Nein danke" }).click();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: /^Hallo/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Benachrichtigungen aufs Handy?" })).toBeHidden();
  await context.close();
});

test("Klick auf den eigenen Benutzer in der Seitenleiste öffnet „Meine Anmeldung“", async ({ browser }) => {
  const context = await browser.newContext({ storageState: ADMIN_STATE });
  const page = await context.newPage();
  await page.goto("/");
  await page.getByRole("link", { name: /^Meine Anmeldung: .*admin@test\.local/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Meine Anmeldung" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Meine Anmeldung:/ })).toHaveAttribute("aria-current", "page");
  await context.close();
});

test("Umschalter zwischen hellem und dunklem Design merkt sich die Wahl", async ({ page }) => {
  await page.goto("/anmeldung/login/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "wtsv-light");
  const toggle = page.getByRole("checkbox", { name: "Dunkles Design" });
  await page.locator("label:has(input.theme-controller)").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "wtsv-dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "wtsv-dark");
  await expect(toggle).toBeChecked();
});

test("Seitenleiste am Handy: öffnet über das Menü und schließt mit Escape", async ({ browser }) => {
  const context = await browser.newContext({ storageState: ADMIN_STATE, viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto("/");
  const navigation = page.getByRole("navigation", { name: "Hauptnavigation" });
  await expect(navigation).toBeHidden();
  await page.getByRole("button", { name: "Navigation öffnen" }).click();
  await expect(navigation.getByRole("link", { name: "Benutzer" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(navigation).toBeHidden();
  await context.close();
});

test("Hauptaktion am Handy verdeckt den Footer nicht", async ({ browser }) => {
  const context = await browser.newContext({ storageState: ADMIN_STATE, viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto("/verwaltung/benutzer/einladen/");
  const footer = page.locator("footer");
  await footer.scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const footerBox = await footer.boundingBox();
  const barBox = await page.locator(".action-bar").boundingBox();
  expect(footerBox && barBox).toBeTruthy();
  expect(footerBox!.y + footerBox!.height).toBeLessThanOrEqual(barBox!.y + 1);
  await context.close();
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

test("Uke beantwortet eine Frage ohne Neuladen und zeigt Links zu den Terminen", async ({ browser }) => {
  // In den Tests antwortet statt eines Sprachmodells PORTAL_ASSISTANT_URL=fake (feste Antworten, echte Werkzeuge)
  const context = await browser.newContext({ storageState: ADMIN_STATE });
  const page = await context.newPage();
  await page.goto("/uke/");
  const log = page.getByRole("log", { name: "Gespräch mit Uke" });
  await page.getByLabel("Deine Frage").fill("Welche Termine gibt es?");
  await page.getByLabel("Deine Frage").press("Enter");
  await expect(log.getByText("Welche Termine gibt es?")).toBeVisible();
  await expect(log.getByText(/Termine gefunden|keine Termine gefunden/)).toBeVisible();
  await expect(page.getByLabel("Deine Frage")).toHaveValue("");
  await expectNoA11yViolations(page);
  // Nach dem Neuladen steht das Gespräch noch da; „Neues Gespräch“ fängt von vorn an
  await page.reload();
  await expect(log.getByText("Welche Termine gibt es?")).toBeVisible();
  await page.getByRole("button", { name: "Neues Gespräch" }).click();
  await expect(log.getByText("Welche Termine gibt es?")).toHaveCount(0);
  await context.close();
});

test("Uke öffnet sich von jeder Seite als Fenster, ohne die Seite zu sperren", async ({ browser }) => {
  const context = await browser.newContext({ storageState: ADMIN_STATE, viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  await page.goto("/termine/");
  const fab = page.getByRole("button", { name: "Uke fragen" });
  await expect(fab).toHaveAttribute("aria-expanded", "false");
  await fab.click();
  const panel = page.getByRole("dialog", { name: /Uke/ });
  await expect(panel).toBeVisible();
  await expect(fab).toHaveAttribute("aria-expanded", "true");
  await expect(panel.getByLabel("Deine Frage")).toBeFocused();
  await panel.getByLabel("Deine Frage").fill("Welche Termine gibt es?");
  await panel.getByRole("button", { name: "Senden" }).click();
  await expect(panel.getByText(/Termine gefunden|keine Termine gefunden/)).toBeVisible();
  await expectNoA11yViolations(page);
  // Nicht-modal: die Seite dahinter bleibt bedienbar, und beim Seitenwechsel ist das Gespräch wieder offen
  await page.getByRole("link", { name: "Hilfe" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Hilfe" })).toBeVisible();
  await expect(panel.getByText("Welche Termine gibt es?")).toBeVisible();
  // Escape schließt, der Fokus geht zurück auf den Knopf
  await panel.getByLabel("Deine Frage").press("Escape");
  await expect(panel).toBeHidden();
  await expect(fab).toBeFocused();
  await page.reload();
  await expect(panel).toBeHidden();
  await context.close();
});

test("Uke am Handy: Knopf über der Aktionsleiste, Fenster füllt den Bildschirm", async ({ browser }) => {
  const context = await browser.newContext({ storageState: ADMIN_STATE, viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  await page.goto("/mitglieder/");
  const fab = page.getByRole("button", { name: "Uke fragen" });
  const bar = page.locator(".action-bar");
  const fabBox = await fab.boundingBox();
  const barBox = await bar.boundingBox();
  expect(fabBox!.y + fabBox!.height).toBeLessThanOrEqual(barBox!.y);
  await fab.click();
  const panel = page.getByRole("dialog", { name: /Uke/ });
  await expect(panel).toBeVisible();
  const box = await panel.boundingBox();
  expect(box!.width).toBe(390);
  await panel.getByRole("button", { name: "Schließen" }).click();
  await expect(panel).toBeHidden();
  await context.close();
});
