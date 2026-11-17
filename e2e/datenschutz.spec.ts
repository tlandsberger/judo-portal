import { expect, test } from "@playwright/test";
import { ADMIN_STATE, acceptInvitation, expectNoA11yViolations, moreAction, openMoreActions, setPassword } from "./helpers";

const PARENT = { email: "paula@test.local", password: "Sicher-Eltern-864" };

test("Protokoll, Auskunft für Eltern und Löschen eines Mitglieds mit Bestätigung", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();

  // Kind anlegen und ändern: beides steht im Protokoll
  await admin.goto("/mitglieder/neu/");
  await admin.getByLabel("Vorname").fill("Paul");
  await admin.getByLabel("Nachname").fill("Protokoll");
  await admin.getByLabel("Geburtsdatum").fill("2016-05-01");
  await admin.getByRole("button", { name: "Speichern" }).click();
  await admin.getByRole("link", { name: "Bearbeiten" }).click();
  await admin.getByLabel("Telefon").fill("040 123456");
  await admin.getByRole("button", { name: "Speichern" }).click();
  const changes = admin.getByRole("region", { name: "Letzte Änderungen" });
  await expect(changes.getByText("Paul Protokoll geändert: Telefon")).toBeVisible();
  await expect(changes.getByText("Paul Protokoll angelegt")).toBeVisible();
  await expectNoA11yViolations(admin);

  // Elternteil einladen
  await admin.getByLabel("Elternteil").check();
  await admin.getByLabel("E-Mail").fill(PARENT.email);
  await admin.getByRole("button", { name: "Zugang geben" }).click();
  const memberUrl = admin.url();
  const parentContext = await browser.newContext();
  const parent = await parentContext.newPage();
  await acceptInvitation(parent, PARENT.email);
  await setPassword(parent, PARENT.password);

  // Auskunft unter „Meine Daten“
  await parent.goto("/meine-daten/");
  await moreAction(parent, "link", "Datenauskunft (Art. 15 DSGVO)");
  await expect(parent.getByRole("heading", { level: 1, name: "Datenauskunft (Art. 15 DSGVO)" })).toBeVisible();
  await expect(parent.getByRole("heading", { name: "Paul Protokoll" })).toBeVisible();
  await expectNoA11yViolations(parent);
  const download = parent.waitForEvent("download");
  await parent.getByRole("link", { name: "Als PDF herunterladen" }).click();
  expect((await download).suggestedFilename()).toMatch(/^datenauskunft-\d{4}-\d{2}-\d{2}\.pdf$/);

  // Den eigenen Zugang löschen: Paul bleibt erhalten
  await parent.goto("/zugang/anmeldung/");
  await openMoreActions(parent);
  await expectNoA11yViolations(parent); // mit geöffnetem Menü
  await parent.getByRole("link", { name: "Meinen Zugang löschen" }).click();
  await expect(parent.getByText("Paul Protokoll (Erziehungsberechtigt)")).toBeVisible();
  await expectNoA11yViolations(parent);
  await parent.getByLabel("Ich habe verstanden, dass die Daten endgültig gelöscht werden.").check();
  await parent.getByRole("button", { name: "Zugang endgültig löschen" }).click();
  await expect(parent.getByText("Dein Zugang ist gelöscht.")).toBeVisible();
  await admin.reload();
  await expect(admin.getByRole("heading", { level: 1, name: "Paul Protokoll" })).toBeVisible();
  await expect(admin.getByRole("region", { name: "Zugänge" }).getByText(PARENT.email)).toHaveCount(0);

  // Protokoll-Seite
  await admin.goto("/protokoll/");
  await expect(admin.getByText(`Einladung an ${PARENT.email} für Paul Protokoll (Erziehungsberechtigt)`)).toBeVisible();
  await expectNoA11yViolations(admin);

  // Löschen mit Bestätigung: der Elternteil hat danach kein Mitglied mehr und wird mitgelöscht
  await admin.goto(memberUrl);
  await moreAction(admin, "link", "Mitglied löschen");
  await expectNoA11yViolations(admin);
  await admin.getByRole("button", { name: "Endgültig löschen" }).click();
  await expect(admin.getByLabel("Ich habe verstanden, dass die Daten endgültig gelöscht werden.")).toBeVisible();
  await admin.getByLabel("Ich habe verstanden, dass die Daten endgültig gelöscht werden.").check();
  await admin.getByRole("button", { name: "Endgültig löschen" }).click();
  await expect(admin.getByText("Paul Protokoll ist gelöscht.")).toBeVisible();
  await admin.goto("/protokoll/");
  await expect(admin.getByText("Mitglied ohne Nummer gelöscht (auf Wunsch)")).toBeVisible();
  await expect(admin.getByText("Paul Protokoll angelegt")).toHaveCount(0);

  await parentContext.close();
  await admin.context().close();
});
