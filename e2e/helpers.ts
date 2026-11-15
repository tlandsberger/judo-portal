import AxeBuilder from "@axe-core/playwright";
import { expect, type BrowserContext, type Page } from "@playwright/test";
import { readdirSync, readFileSync, statSync } from "node:fs";

export const MAIL_DIR = process.env.MAIL_DIR ?? "data/mails";
export const ADMIN = { email: "admin@test.local", password: "Sicher-Admin-123" };
export const ADMIN_STATE = "test-results/.auth/admin.json";

/** Neueste Mail (Dateien des filebased-Backends) an eine Adresse. */
export function lastMailTo(email: string): string {
  // Neueste zuerst nach Änderungszeit: Dateinamen enthalten nur Sekunden, zwei Mails derselben Sekunde stünden sonst zufällig
  const modified = (file: string) => statSync(`${MAIL_DIR}/${file}`, { bigint: true }).mtimeNs;
  const files = readdirSync(MAIL_DIR).sort((a, b) => (modified(a) < modified(b) ? 1 : modified(a) > modified(b) ? -1 : 0));
  for (const file of files) {
    const content = readFileSync(`${MAIL_DIR}/${file}`, "utf8");
    const messages = content.split(/^-{70,}$/m).reverse();
    const hit = messages.find((m) => new RegExp(`^To: ${email}$`, "mi").test(m));
    if (hit) return hit.replace(/=\r?\n/g, "").replace(/=([0-9A-F]{2})/g, (_, h) => String.fromCharCode(parseInt(h, 16)));
  }
  throw new Error(`Keine Mail an ${email} gefunden`);
}

export function invitationLink(email: string): string {
  const match = lastMailTo(email).match(/https?:\/\/\S+\/einladung\/[\w-]+\//);
  if (!match) throw new Error("Kein Einladungslink in der Mail");
  return new URL(match[0]).pathname;
}

export function loginCode(email: string): string {
  const match = lastMailTo(email).match(/^\s*([A-Z0-9]{4}-[A-Z0-9]{4})\s*$/m);
  if (!match) throw new Error("Kein Anmeldecode in der Mail");
  return match[1];
}

/** Virtueller Passkey (Plattform-Authenticator) für den Browser-Kontext. */
export async function addVirtualAuthenticator(context: BrowserContext, page: Page) {
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true },
  });
}

export async function loginWithPassword(page: Page, email: string, password: string) {
  await page.goto("/anmeldung/login/");
  await page.getByLabel("E-Mail-Adresse").fill(email);
  await page.getByLabel("Passwort", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Mit Passwort anmelden" }).click();
  await expect(page).toHaveURL(/\/$/);
}

export async function logout(page: Page) {
  // Abmelden steht unten in der Seitenleiste (am Desktop immer sichtbar)
  await page.getByRole("button", { name: "Abmelden" }).click();
  await expect(page.getByRole("button", { name: "Mit Passkey anmelden" })).toBeVisible();
  // Erst wenn alle Skripte geladen sind, hängt der Passkey-Button an der Anmeldung per WebAuthn
  await page.waitForLoadState("networkidle");
}

export async function acceptInvitation(page: Page, email: string) {
  await page.goto(invitationLink(email));
  await page.getByRole("button", { name: "Einladung annehmen" }).click();
  await expect(page.getByRole("heading", { name: "Wie möchtest du dich anmelden?" })).toBeVisible();
}

export async function setPassword(page: Page, password: string) {
  await page.goto("/anmeldung/password/set/");
  await page.getByLabel("Passwort", { exact: true }).fill(password);
  await page.getByLabel("Passwort (Wiederholung)").fill(password);
  await page.getByRole("button", { name: "Passwort setzen" }).click();
}

export async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(", ")}`)).toEqual([]);
}

/** Importiert die Beispiel-Mitglieder (wiederholbar: beim zweiten Mal ist nichts zu übernehmen). */
export async function importMembers(page: Page) {
  await page.goto("/mitglieder/import/");
  await page.getByLabel("CSV-Datei").setInputFiles("e2e/fixtures/mitglieder.csv");
  await page.getByRole("button", { name: "Vorschau anzeigen" }).click();
  await expect(page.getByRole("heading", { name: "Vorschau des Imports" })).toBeVisible();
  const apply = page.getByRole("button", { name: "Übernehmen" });
  if (await apply.isVisible()) {
    await apply.click();
    await expect(page.getByRole("heading", { level: 1, name: "Mitglieder" })).toBeVisible();
  }
}

/** Zielgruppe „Kinder und Jugend“ (bis 18) anlegen, falls es sie noch nicht gibt. */
export async function ensureYouthGroup(page: Page) {
  await page.goto("/zielgruppen/");
  if (await page.getByRole("link", { name: "Kinder und Jugend" }).count()) return;
  await page.getByRole("link", { name: "Zielgruppe anlegen" }).click();
  await page.getByLabel("Name").fill("Kinder und Jugend");
  await page.getByLabel("Alter bis").fill("18");
  await page.getByRole("button", { name: "Speichern" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Kinder und Jugend" })).toBeVisible();
}

/** Datum in n Tagen für Felder vom Typ datetime-local, z. B. „2026-11-25T10:00“. */
export function localDateTime(days: number, time: string): string {
  const day = new Date(Date.now() + days * 86_400_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}T${time}`;
}

/** Headless-Chromium meldet Benachrichtigungen immer als „denied“. Für Tests wie ein frischer Browser: „default“. */
export async function freshNotificationPermission(context: BrowserContext) {
  await context.addInitScript(() => {
    Object.defineProperty(Notification, "permission", { get: () => "default" });
  });
}
