import { expect, test } from "@playwright/test";
import {
  ADMIN,
  ADMIN_STATE,
  acceptInvitation,
  addVirtualAuthenticator,
  expectNoA11yViolations,
  loginCode,
  loginWithPassword,
  logout,
} from "./helpers";

test("Anmelden mit Passwort und per Code aus der Mail", async ({ page }) => {
  await loginWithPassword(page, ADMIN.email, ADMIN.password);
  await expect(page.getByRole("heading", { name: /^Hallo/ })).toBeVisible();
  await logout(page);

  await page.getByRole("link", { name: "Anmeldecode per E-Mail" }).click();
  await page.getByLabel("E-Mail-Adresse").fill(ADMIN.email);
  await page.getByRole("button", { name: "Code anfordern" }).click();
  await page.getByLabel("Code").fill(loginCode(ADMIN.email));
  await page.getByRole("button", { name: "Bestätigen" }).click();
  await expect(page.getByRole("heading", { name: /^Hallo/ })).toBeVisible();
});

test("Falsches Passwort wird abgelehnt", async ({ page }) => {
  await page.goto("/anmeldung/login/");
  await page.getByLabel("E-Mail-Adresse").fill(ADMIN.email);
  await page.getByLabel("Passwort", { exact: true }).fill("falsch-falsch");
  await page.getByRole("button", { name: "Mit Passwort anmelden" }).click();
  await expect(page.getByText(/nicht korrekt|falsch/i)).toBeVisible();
});

test.describe("Einladung", () => {
  test("Übungsleiter wird eingeladen, richtet einen Passkey ein und meldet sich damit an", async ({ browser }) => {
    const email = `trainer-${Date.now()}@test.local`;
    const admin = await browser.newContext({ storageState: ADMIN_STATE });
    const adminPage = await admin.newPage();
    await adminPage.goto("/verwaltung/konten/einladen/");
    await expectNoA11yViolations(adminPage);
    await adminPage.getByLabel("E-Mail").fill(email);
    await adminPage.getByLabel("Vorname").fill("Tom");
    await adminPage.getByLabel("Nachname").fill("Trainer");
    await adminPage.getByLabel("Übungsleiter").check();
    await adminPage.getByRole("button", { name: "Einladung senden" }).click();
    await expect(adminPage.getByText(`Einladung an ${email} verschickt.`)).toBeVisible();
    await admin.close();

    // Ein Mail-Scanner öffnet den Link zuerst und klickt „Einladung annehmen“ – das darf nichts kaputt machen.
    const scanner = await browser.newContext();
    const scannerPage = await scanner.newPage();
    await acceptInvitation(scannerPage, email);
    await scannerPage.goto("/verwaltung/konten/");
    await expect(scannerPage).toHaveURL(/\/konto\/einrichten\/$/);

    const context = await browser.newContext();
    const page = await context.newPage();
    await addVirtualAuthenticator(context, page);
    await acceptInvitation(page, email);
    await expectNoA11yViolations(page);

    await page.getByRole("link", { name: "Passkey hinzufügen" }).click();
    await page.getByLabel("Name").fill("Testgerät");
    await page.getByRole("button", { name: "Passkey anlegen" }).click();
    await expect(page.getByText("1 Passkey eingerichtet.")).toBeVisible();

    await logout(page);
    await page.getByRole("button", { name: "Mit Passkey anmelden" }).click();
    await expect(page.getByRole("heading", { name: "Hallo Tom" })).toBeVisible();
    // Übungsleiter verwalten keine Konten
    await expect(page.getByRole("link", { name: "Konten" })).toHaveCount(0);
    expect((await page.goto("/verwaltung/konten/"))?.status()).toBe(403);
    await context.close();

    // Die Sitzung des Scanners kommt nie über die Einrichtung hinaus.
    await scannerPage.goto("/");
    await expect(scannerPage).toHaveURL(/\/anmeldung\/login\//);
    await expect(scannerPage.getByRole("heading", { name: /^Hallo/ })).toHaveCount(0);
    await scanner.close();
  });
});

test("Einladungslink ohne Mail erstellen und weitergeben", async ({ browser }) => {
  const email = `link-${Date.now()}@test.local`;
  const admin = await browser.newContext({ storageState: ADMIN_STATE });
  const adminPage = await admin.newPage();
  await adminPage.goto("/verwaltung/konten/einladen/");
  await adminPage.getByLabel("E-Mail").fill(email);
  await adminPage.getByRole("button", { name: "Nur Link erstellen" }).click();
  await expect(adminPage.getByRole("heading", { name: "Einladungslink" })).toBeVisible();
  await expectNoA11yViolations(adminPage);
  const link = await adminPage.getByLabel("Link").inputValue();
  expect(link).toContain("/einladung/");
  await admin.close();

  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(new URL(link).pathname);
  await page.getByRole("button", { name: "Einladung annehmen" }).click();
  await expect(page.getByRole("heading", { name: "Wie möchtest du dich anmelden?" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Lieber per Code anmelden" })).toBeVisible();
  await context.close();
});
