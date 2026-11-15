import { expect, test } from "@playwright/test";
import { ADMIN_STATE, acceptInvitation, expectNoA11yViolations, importMembers, setPassword } from "./helpers";

const PARENT = { email: "eltern@test.local", password: "Sicher-Eltern-123" };

test("CSV importieren, Elternteil für zwei Kinder einladen, Daten selbst pflegen", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();

  // Vorschau zeigt, was passiert, gespeichert wird erst mit „Übernehmen“
  await admin.goto("/mitglieder/import/");
  await admin.getByLabel("CSV-Datei").setInputFiles("e2e/fixtures/mitglieder.csv");
  await admin.getByRole("button", { name: "Vorschau anzeigen" }).click();
  await expect(admin.getByText("4 neu")).toBeVisible();
  await expectNoA11yViolations(admin);
  await admin.getByRole("button", { name: "Übernehmen" }).click();
  await expect(admin.getByText("Import abgeschlossen: 4 neu, 0 aktualisiert.")).toBeVisible();
  await expect(admin.getByRole("link", { name: "Muster, Mia" })).toBeVisible();

  // Ein zweiter Import derselben Datei ändert nichts
  await importMembers(admin);
  await expect(admin.getByText("4 unverändert")).toBeVisible();

  // Für beide Kinder denselben Elternteil einladen: eine Einladung, zwei Verknüpfungen
  for (const name of ["Muster, Mia", "Beispiel, Ben"]) {
    await admin.goto("/mitglieder/");
    await admin.getByRole("link", { name }).click();
    await admin.getByLabel("Elternteil").check();
    await admin.getByLabel("E-Mail").fill(PARENT.email);
    await admin.getByRole("button", { name: "Zugang geben" }).click();
    await expect(admin.getByText(`Einladung an ${PARENT.email} verschickt.`)).toBeVisible();
    await expect(admin.getByText("eingeladen, noch nicht angenommen")).toBeVisible();
  }
  await expectNoA11yViolations(admin);

  // Der Elternteil nimmt an und sieht beide Kinder, das ältere zuerst
  const context = await browser.newContext();
  const parent = await context.newPage();
  await acceptInvitation(parent, PARENT.email);
  await setPassword(parent, PARENT.password);
  await parent.goto("/meine-daten/");
  const cards = parent.getByRole("heading", { level: 2 });
  await expect(cards).toHaveText(["Ben Beispiel", "Mia Muster"]);
  await expectNoA11yViolations(parent);

  await parent.getByRole("link", { name: /Mia Muster/ }).click();
  await expect(parent.getByText("24,5 kg")).toBeVisible();
  await parent.getByRole("link", { name: "Bearbeiten" }).click();
  await parent.getByLabel("Gewicht (kg)").fill("25,8");
  await parent.getByLabel("Graduierung").selectOption({ label: "6. Kyu (gelb-orange)" });
  await expectNoA11yViolations(parent);
  await parent.getByRole("button", { name: "Speichern" }).click();
  await expect(parent.getByText("Deine Änderungen sind gespeichert.")).toBeVisible();
  await expect(parent.getByText("25,8 kg")).toBeVisible();
  await expect(parent.getByText("6. Kyu (gelb-orange)")).toBeVisible();
  // Die Mitgliederliste bleibt der Abteilungsleitung vorbehalten
  expect((await parent.goto("/mitglieder/"))?.status()).toBe(403);
  await context.close();

  // Die Abteilungsleitung sieht die Verknüpfung
  await admin.goto("/mitglieder/");
  await admin.getByRole("link", { name: "Muster, Mia" }).click();
  await expect(admin.getByText(`Erziehungsberechtigt · ${PARENT.email}`)).toBeVisible();
  await admin.context().close();
});
