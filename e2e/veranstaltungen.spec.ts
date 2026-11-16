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
const TRAINER = { email: "clara@test.local", password: "Sicher-Trainer-789" };
const PARENTS = { email: "eltern-zwei@test.local", password: "Sicher-Eltern-321" };

test("Lehrgang anlegen, Team eintragen, Kind mit Gewicht anmelden, Trainerin sieht Teilnehmer und bestätigt Stunden", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();
  await importMembers(admin);
  await ensureYouthGroup(admin);
  await expect(admin.getByText("Passen heute: 3")).toBeVisible();

  // Übungsleiterin einladen und mit ihrem Mitgliedsprofil verknüpfen (Voraussetzung für Team-Rollen)
  await admin.goto("/verwaltung/benutzer/einladen/");
  await admin.getByLabel("E-Mail").fill(TRAINER.email);
  await admin.getByLabel("Vorname").fill("Clara");
  await admin.getByLabel("Nachname").fill("Clever");
  await admin.getByLabel("Übungsleiter").check();
  await admin.getByRole("button", { name: "Einladung senden" }).click();
  const trainerContext = await browser.newContext();
  const trainer = await trainerContext.newPage();
  await acceptInvitation(trainer, TRAINER.email);
  await setPassword(trainer, TRAINER.password);
  await admin.goto("/mitglieder/");
  await admin.getByRole("link", { name: "Clever, Clara" }).click();
  await admin.getByLabel("Clara selbst").check();
  await admin.getByRole("button", { name: "Zugang geben" }).click();
  await expect(admin.getByText("Eigenes Profil · clara@test.local")).toBeVisible();

  // Rollen: Trainer gibt es bei Lehrgängen, abrechnungsrelevant
  await admin.goto("/rollen/");
  await expect(admin.getByRole("link", { name: "Co-Trainer" })).toBeVisible();
  await expectNoA11yViolations(admin);

  // Lehrgang mit Zielgruppe, Pflichtgewicht, Termin und Team in einem Schritt
  await admin.goto("/veranstaltungen/neu/");
  await admin.getByLabel("Titel").fill("Randori-Lehrgang");
  await admin.getByLabel("Art").selectOption({ label: "Lehrgang" });
  await admin.getByLabel("Kinder und Jugend").check();
  await admin.getByLabel("Gewicht bei Anmeldung erforderlich").check();
  await admin.getByLabel("Einmalig").check();
  await expect(admin.getByLabel("Wochentage")).toBeHidden();
  await admin.getByLabel("Beginn", { exact: true }).fill(localDateTime(10, "10:00"));
  await admin.getByLabel("Ende", { exact: true }).fill(localDateTime(10, "14:00"));
  await admin.getByLabel("Mitglied").selectOption({ label: "Clara Clever" });
  await admin.getByLabel("Rolle").selectOption({ label: "Trainer" });
  await expectNoA11yViolations(admin);
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByText("„Randori-Lehrgang“ angelegt mit 1 Termin.")).toBeVisible();
  await expectNoA11yViolations(admin);

  // Ein weiterer, schon vergangener Termin; das Team kommt am Termin dazu
  await admin.getByRole("link", { name: "Termin", exact: true }).click();
  await admin.getByLabel("Beginn", { exact: true }).fill(localDateTime(-1, "10:00"));
  await admin.getByLabel("Ende", { exact: true }).fill(localDateTime(-1, "14:00"));
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByText("Termin angelegt. Trag hier das Team ein.")).toBeVisible();
  await admin.getByLabel("Mitglied").selectOption({ label: "Clara Clever" });
  await admin.getByLabel("Rolle").selectOption({ label: "Trainer" });
  await admin.getByRole("button", { name: "Eintragen oder Rolle ändern" }).click();
  await expect(admin.getByText("Clara Clever ist als Trainer eingetragen.")).toBeVisible();
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
  await parent.getByRole("link", { name: /Mia für Randori-Lehrgang am .* anmelden/ }).click();
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

  // Trainerin: Teilnehmer mit Notfallkontakt, Stunden des vergangenen Termins bestätigen
  await trainer.goto("/stunden/");
  await expectNoA11yViolations(trainer);
  await trainer.getByRole("region", { name: "Kommende" }).getByRole("link", { name: "Randori-Lehrgang" }).click();
  await expect(trainer.getByRole("heading", { name: "Teilnehmer (1)" })).toBeVisible();
  await expect(trainer.getByText("„kommt mit dem Bus“")).toBeVisible();
  await expect(trainer.getByRole("link", { name: PARENT.email })).toBeVisible();
  await expectNoA11yViolations(trainer);
  // Mitglieder sieht sie sonst nicht
  expect((await trainer.goto("/mitglieder/"))?.status()).toBe(403);
  await trainer.goto("/stunden/");
  await trainer.getByRole("button", { name: /Randori-Lehrgang am .* bestätigen/ }).click();
  await expect(trainer.getByText("Danke, deine Stunden sind bestätigt.")).toBeVisible();
  await expect(trainer.getByText("bestätigt · 240 Min.")).toBeVisible();
  await expectNoA11yViolations(trainer);
  await trainerContext.close();
  await admin.context().close();
});

test("Training wiederkehrend anlegen; Elternteil mit zwei Kindern sieht jeden Termin einmal", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();
  await importMembers(admin);
  await ensureYouthGroup(admin);

  await admin.goto("/veranstaltungen/neu/");
  await admin.getByLabel("Titel").fill("Kindertraining");
  await admin.getByLabel("Art").selectOption({ label: "Training" });
  await admin.getByLabel("Kinder und Jugend").check();
  await admin.getByLabel("Wiederkehrend").check();
  await expect(admin.getByLabel("Beginn", { exact: true })).toBeHidden();
  await admin.getByLabel("Dienstag").check();
  await admin.getByLabel("Donnerstag").check();
  await admin.getByLabel("Uhrzeit von").fill("17:00");
  await admin.getByLabel("Uhrzeit bis").fill("18:30");
  await admin.getByLabel("Gültig bis").fill(localDateTime(27, "00:00").slice(0, 10));
  await admin.getByLabel("Anmeldung schließt (Stunden vorher)").fill("2");
  await admin.getByLabel("Mitglied").selectOption({ label: "Clara Clever" });
  await admin.getByLabel("Rolle").selectOption({ label: "Co-Trainer" });
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByText(/„Kindertraining“ angelegt mit \d+ Terminen\./)).toBeVisible();
  await expect(admin.getByRole("heading", { name: "Dienstag 17:00–18:30" })).toBeVisible();
  await expect(admin.getByRole("heading", { name: "Donnerstag 17:00–18:30" })).toBeVisible();
  await expectNoA11yViolations(admin);

  // Ein Elternteil für Ben und David
  await admin.goto("/mitglieder/");
  await admin.getByRole("link", { name: "Beispiel, Ben" }).click();
  await admin.getByLabel("Elternteil").check();
  await admin.getByLabel("E-Mail").fill(PARENTS.email);
  await admin.getByRole("button", { name: "Zugang geben" }).click();
  const parentContext = await browser.newContext();
  const parent = await parentContext.newPage();
  await acceptInvitation(parent, PARENTS.email);
  await setPassword(parent, PARENTS.password);
  await admin.goto("/mitglieder/");
  await admin.getByRole("link", { name: "Dachs, David" }).click();
  await admin.getByLabel("Elternteil").check();
  await admin.getByLabel("E-Mail").fill(PARENTS.email);
  await admin.getByRole("button", { name: "Zugang geben" }).click();

  // Jeder Termin einmal, darunter beide Kinder mit eigenem Knopf
  await parent.goto("/");
  const next = parent.getByRole("region", { name: "Nächste Termine" });
  const nextLinks = next.getByRole("link", { name: /^(Kindertraining|Randori-Lehrgang)$/ });
  await expect(nextLinks).toHaveCount(3);
  // drei Termine, in jedem stehen beide Kinder – nicht ein Eintrag je Kind
  await expect(next.getByText("Ben", { exact: true })).toHaveCount(3);
  await expect(next.getByText("David", { exact: true })).toHaveCount(3);
  await parent.goto("/termine/");
  const first = parent.getByRole("listitem").filter({ has: parent.getByRole("link", { name: "Kindertraining" }) }).first();
  await expect(first.getByText("Ben", { exact: true })).toBeVisible();
  await expect(first.getByText("David", { exact: true })).toBeVisible();
  await first.getByRole("button", { name: /^David für Kindertraining/ }).click();
  await expect(parent.getByText("David ist angemeldet.")).toBeVisible();
  await expectNoA11yViolations(parent);
  await parentContext.close();
  await admin.context().close();
});
