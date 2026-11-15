import { expect, test } from "@playwright/test";
import {
  ADMIN_STATE,
  acceptInvitation,
  ensureYouthGroup,
  expectNoA11yViolations,
  importMembers,
  localDateTime,
  setPassword,
} from "./helpers";

const PARENT = { email: "eltern-wk@test.local", password: "Sicher-Eltern-456" };
const TRAINER = { email: "anna@test.local", password: "Sicher-Trainer-789" };

test("Wettkampf anlegen, Kind mit Gewicht anmelden, Übungsleiter sieht Teilnehmer und bestätigt", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();
  await importMembers(admin);
  await ensureYouthGroup(admin);
  await expect(admin.getByText("Passen heute: 3")).toBeVisible();

  // Übungsleiterin einladen
  await admin.goto("/verwaltung/benutzer/einladen/");
  await admin.getByLabel("E-Mail").fill(TRAINER.email);
  await admin.getByLabel("Vorname").fill("Anna");
  await admin.getByLabel("Nachname").fill("Trainer");
  await admin.getByLabel("Übungsleiter").check();
  await admin.getByRole("button", { name: "Einladung senden" }).click();
  const trainerContext = await browser.newContext();
  const trainer = await trainerContext.newPage();
  await acceptInvitation(trainer, TRAINER.email);
  await setPassword(trainer, TRAINER.password);

  // Veranstaltung mit Zielgruppe und Pflichtgewicht, Standard-Team, ein kommender und ein vergangener Termin
  await admin.goto("/veranstaltungen/neu/");
  await admin.getByLabel("Titel").fill("Kinderwettkampf");
  await admin.getByLabel("Art").selectOption({ label: "Wettkampf" });
  await admin.getByLabel("Kinder und Jugend").check();
  await admin.getByLabel("Gewicht bei Anmeldung erforderlich").check();
  await expectNoA11yViolations(admin);
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByRole("heading", { level: 1, name: "Kinderwettkampf" })).toBeVisible();
  await admin.getByLabel("Übungsleiter").selectOption({ label: "Anna Trainer" });
  await admin.getByRole("button", { name: "Ins Standard-Team" }).click();
  for (const [days, time] of [
    [10, "10:00"],
    [-1, "10:00"],
  ] as const) {
    await admin.getByRole("link", { name: "Termin", exact: true }).click();
    await admin.getByLabel("Beginn").fill(localDateTime(days, time));
    await admin.getByLabel("Ende").fill(localDateTime(days, "14:00"));
    await admin.getByRole("button", { name: "Speichern" }).click();
    await expect(admin.getByText("Termin angelegt.")).toBeVisible();
  }
  await expectNoA11yViolations(admin);

  // Beide Termine übernehmen das Standard-Team
  await admin.goto("/termine/");
  await admin.getByRole("link", { name: "Kinderwettkampf" }).click();
  await expect(admin.getByText("Anna Trainer (Trainer)")).toBeVisible();
  await expectNoA11yViolations(admin);

  // Elternteil für Mia einladen
  await admin.goto("/mitglieder/");
  await admin.getByRole("link", { name: "Muster, Mia" }).click();
  await admin.getByLabel("Elternteil").check();
  await admin.getByLabel("E-Mail").fill(PARENT.email);
  await admin.getByRole("button", { name: "Zugang geben" }).click();
  const parentContext = await browser.newContext();
  const parent = await parentContext.newPage();
  await acceptInvitation(parent, PARENT.email);
  await setPassword(parent, PARENT.password);

  // Startseite und „Termine“: passender Wettkampf, Anmeldung mit Gewicht
  await parent.goto("/");
  await expect(parent.getByRole("heading", { name: "Nächste Termine" })).toBeVisible();
  await parent.goto("/termine/");
  await expectNoA11yViolations(parent);
  await parent.getByRole("link", { name: /Mia für Kinderwettkampf am .* anmelden/ }).click();
  await expect(parent.getByLabel("Gewicht (kg)")).not.toHaveValue("");
  await parent.getByLabel("Gewicht (kg)").fill("26,1");
  await parent.getByLabel("Hinweis").fill("kommt mit dem Bus");
  await expectNoA11yViolations(parent);
  await parent.getByRole("button", { name: "Anmelden" }).click();
  await expect(parent.getByText("Mia ist angemeldet.")).toBeVisible();
  await expect(parent.getByText("angemeldet", { exact: true })).toBeVisible();
  await expectNoA11yViolations(parent);
  // Ein Kind: „Meine Daten“ führt direkt zu Mia; das Gewicht ist übernommen
  await parent.goto("/meine-daten/");
  await expect(parent.getByText("26,1 kg")).toBeVisible();
  await parentContext.close();

  // Übungsleiterin: Teilnehmer mit Notfallkontakt, Begleitung des vergangenen Termins bestätigen
  await trainer.goto("/einsaetze/");
  await expectNoA11yViolations(trainer);
  await trainer.getByRole("region", { name: "Kommende" }).getByRole("link", { name: "Kinderwettkampf" }).click();
  await expect(trainer.getByRole("heading", { name: "Teilnehmer (1)" })).toBeVisible();
  await expect(trainer.getByText("„kommt mit dem Bus“")).toBeVisible();
  await expect(trainer.getByRole("link", { name: PARENT.email })).toBeVisible();
  await expectNoA11yViolations(trainer);
  // Mitglieder sieht sie sonst nicht
  expect((await trainer.goto("/mitglieder/"))?.status()).toBe(403);
  await trainer.goto("/einsaetze/");
  await trainer.getByRole("button", { name: /Kinderwettkampf am .* bestätigen/ }).click();
  await expect(trainer.getByText("Danke, deine Begleitung ist bestätigt.")).toBeVisible();
  await expect(trainer.getByText("bestätigt · 240 Min.")).toBeVisible();
  await expectNoA11yViolations(trainer);
  await trainerContext.close();
  await admin.context().close();
});
