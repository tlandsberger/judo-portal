import { expect, test } from "@playwright/test";
// Läuft zuletzt (Dateiname): das neue Mitglied Jana soll Listen und Zählungen der anderen Tests nicht verändern.
import { ADMIN_STATE, acceptInvitation, expectNoA11yViolations, setPassword } from "./helpers";

const PARENT = { email: "jana-eltern@test.local", password: "Sicher-Eltern-975" };
const CHILD = { email: "jana@test.local", password: "Sicher-Jana-531" };

function fifteenYearsAgo(): string {
  const date = new Date();
  date.setFullYear(date.getFullYear() - 15);
  date.setDate(date.getDate() - 10);
  return date.toISOString().slice(0, 10);
}

test("Eltern richten den eigenen Zugang ihres Kindes ab 14 ein", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();
  await admin.goto("/mitglieder/neu/");
  await admin.getByLabel("Vorname").fill("Jana");
  await admin.getByLabel("Nachname").fill("Jugend");
  await admin.getByLabel("Geburtsdatum").fill(fifteenYearsAgo());
  await admin.getByRole("button", { name: "Speichern" }).click();
  await admin.getByLabel("Elternteil").check();
  await admin.getByLabel("E-Mail").fill(PARENT.email);
  await admin.getByRole("button", { name: "Zugang geben" }).click();

  // Der Elternteil sieht auf der Startseite das Banner
  const parentContext = await browser.newContext();
  const parent = await parentContext.newPage();
  await acceptInvitation(parent, PARENT.email);
  await setPassword(parent, PARENT.password);
  await parent.goto("/");
  await expect(parent.getByText("Jana ist 15 Jahre alt und kann einen eigenen Zugang bekommen.", { exact: false })).toBeVisible();
  await expectNoA11yViolations(parent);

  // E-Mail-Adresse eingeben, die normale Einladung geht an Jana
  await parent.getByRole("link", { name: "Zugang einrichten" }).click();
  await expect(parent.getByRole("heading", { level: 1, name: "Eigener Zugang für Jana" })).toBeVisible();
  await expect(parent.getByLabel("Auch in die Mitgliedsdaten von Jana übernehmen")).toBeChecked();
  await expectNoA11yViolations(parent);
  await parent.getByLabel("E-Mail-Adresse von Jana").fill(PARENT.email);
  await parent.getByRole("button", { name: "Einladen" }).click();
  await expect(parent.getByText("Zu dieser Adresse gibt es schon einen Benutzer.", { exact: false })).toBeVisible();
  await parent.getByLabel("E-Mail-Adresse von Jana").fill(CHILD.email);
  await parent.getByRole("button", { name: "Einladen" }).click();
  await expect(parent.getByText(`Die Einladung an ${CHILD.email} ist unterwegs.`)).toBeVisible();
  await expect(parent.getByText(`Die Einladung an ${CHILD.email} ist verschickt`, { exact: false })).toBeVisible();
  await parent.goto("/");
  await expect(parent.getByText("kann einen eigenen Zugang bekommen", { exact: false })).toHaveCount(0);

  // Jana nimmt an und sieht die eigenen Daten
  const childContext = await browser.newContext();
  const child = await childContext.newPage();
  await acceptInvitation(child, CHILD.email);
  await setPassword(child, CHILD.password);
  await child.goto("/meine-daten/");
  await expect(child.getByRole("heading", { level: 1, name: "Jana Jugend" })).toBeVisible();
  // Die Adresse steht dank Häkchen auch in den Mitgliedsdaten
  await expect(child.getByRole("link", { name: CHILD.email, exact: true })).toBeVisible();

  // Die Eltern sehen weiter Janas Daten, jetzt mit eigenem Zugang
  await parent.goto("/meine-daten/");
  await expect(parent.getByText(`Jana hat einen eigenen Zugang (${CHILD.email}).`)).toBeVisible();
  await parentContext.close();
  await childContext.close();
});
