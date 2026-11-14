import AxeBuilder from "@axe-core/playwright";
import { expect, type BrowserContext, type Page } from "@playwright/test";
import { readdirSync, readFileSync } from "node:fs";

export const MAIL_DIR = process.env.MAIL_DIR ?? "data/mails";
export const ADMIN = { email: "admin@test.local", password: "Sicher-Admin-123" };
export const ADMIN_STATE = "test-results/.auth/admin.json";

/** Neueste Mail (Dateien des filebased-Backends) an eine Adresse. */
export function lastMailTo(email: string): string {
  const files = readdirSync(MAIL_DIR).sort().reverse();
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
  await page.getByRole("button", { name: /Benutzermenü/ }).click();
  await page.getByRole("button", { name: "Abmelden" }).click();
  await expect(page.getByRole("button", { name: "Mit Passkey anmelden" })).toBeVisible();
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
