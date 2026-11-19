import { expect, test } from "@playwright/test";
import {
  ADMIN,
  ADMIN_STATE,
  acceptInvitation,
  addVirtualAuthenticator,
  expectNoA11yViolations,
  lastMailTo,
  loginCode,
  loginWithPassword,
  logout,
  setPassword,
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
    await adminPage.goto("/verwaltung/benutzer/einladen/");
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
    await scannerPage.goto("/verwaltung/benutzer/");
    await expect(scannerPage).toHaveURL(/\/zugang\/einrichten\/$/);

    const context = await browser.newContext();
    const page = await context.newPage();
    await addVirtualAuthenticator(context, page);
    await acceptInvitation(page, email);
    await expectNoA11yViolations(page);

    await page.getByRole("link", { name: "Hinzufügen", exact: true }).click();
    await page.getByLabel("Name").fill("Testgerät");
    await page.getByRole("button", { name: "Passkey anlegen" }).click();
    await expect(page.getByText("1 Passkey eingerichtet.")).toBeVisible();

    await logout(page);
    await page.getByRole("button", { name: "Mit Passkey anmelden" }).click();
    await expect(page.getByRole("heading", { name: "Hallo Tom" })).toBeVisible();
    // Übungsleiter verwalten keine Benutzer
    await expect(page.getByRole("link", { name: "Benutzer" })).toHaveCount(0);
    expect((await page.goto("/verwaltung/benutzer/"))?.status()).toBe(403);
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
  await adminPage.goto("/verwaltung/benutzer/einladen/");
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

test("E-Mail-Adresse ändern: gilt erst nach Bestätigung, danach Anmeldung mit der neuen Adresse", async ({ browser }) => {
  const stamp = Date.now();
  const oldEmail = `wechsel-${stamp}@test.local`;
  const newEmail = `neu-${stamp}@test.local`;
  const admin = await browser.newContext({ storageState: ADMIN_STATE });
  const adminPage = await admin.newPage();
  await adminPage.goto("/verwaltung/benutzer/einladen/");
  await adminPage.getByLabel("E-Mail").fill(oldEmail);
  await adminPage.getByLabel("Vorname").fill("Wera");
  await adminPage.getByRole("button", { name: "Einladung senden" }).click();
  await admin.close();

  const context = await browser.newContext();
  const page = await context.newPage();
  await acceptInvitation(page, oldEmail);
  await setPassword(page, "Sicher-12345!");
  await page.goto("/zugang/anmeldung/");
  await page.getByLabel("Neue E-Mail-Adresse").fill(newEmail);
  await page.getByRole("button", { name: "E-Mail-Adresse ändern" }).click();
  await expect(page.getByText(`Wir haben einen Link an ${newEmail} geschickt.`)).toBeVisible();
  await expect(page.getByText("wartet auf Bestätigung")).toBeVisible();
  await expect(page.getByText(`Angemeldet als ${oldEmail}`)).toBeVisible();
  await expectNoA11yViolations(page);

  const link = lastMailTo(newEmail).match(/https?:\/\/\S+\/zugang\/e-mail\/[\w-]+\//);
  expect(link).not.toBeNull();
  await page.goto(new URL(link![0]).pathname);
  await expect(page.getByRole("heading", { name: "Neue E-Mail-Adresse bestätigen" })).toBeVisible();
  await expectNoA11yViolations(page);
  await page.getByRole("button", { name: "Bestätigen" }).click();
  await expect(page.getByText(`Deine E-Mail-Adresse ist jetzt ${newEmail}.`)).toBeVisible();
  expect(lastMailTo(oldEmail)).toContain(newEmail);

  await logout(page);
  await loginWithPassword(page, newEmail, "Sicher-12345!");
  await expect(page.getByRole("heading", { name: "Hallo Wera" })).toBeVisible();
  await context.close();
});
