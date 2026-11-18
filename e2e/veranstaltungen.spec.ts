import { expect, test } from "@playwright/test";
import {
  ADMIN_STATE,
  acceptInvitation,
  billingMonthPath,
  ensureYouthGroup,
  expectNoA11yViolations,
  importMembers,
  lastMailTo,
  localDateTime,
  setPassword,
} from "./helpers";

const PARENT = { email: "eltern-wk@test.local", password: "Sicher-Eltern-456" };
const TRAINER = { email: "clara@test.local", password: "Sicher-Trainer-789" };
const PARENTS = { email: "eltern-zwei@test.local", password: "Sicher-Eltern-321" };
const GUEST = { email: "lena-gast@test.local" };

test("Lehrgang anlegen, Übungsleiter eintragen, Kind mit Gewicht anmelden, Trainerin sieht Teilnehmer und bestätigt Stunden", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();
  await importMembers(admin);
  await ensureYouthGroup(admin);
  await expect(admin.getByText("Passen heute: 3")).toBeVisible();

  // Übungsleiterin einladen und mit ihrem Mitgliedsprofil verknüpfen (Voraussetzung für Übungsleiter-Rollen)
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

  // Lehrgang mit Zielgruppe, Pflichtgewicht, Termin und Übungsleiterin in einem Schritt
  await admin.goto("/veranstaltungen/neu/");
  await admin.getByLabel("Titel").fill("Randori-Lehrgang");
  await admin.getByLabel("Art").selectOption({ label: "Lehrgang" });
  await admin.getByLabel("Aus Vorlage übernehmen").selectOption({ label: "Kinder und Jugend" });
  await admin.getByRole("button", { name: "Übernehmen" }).click();
  await expect(admin.getByLabel("Bezeichnung")).toHaveValue("Kinder und Jugend");
  await expect(admin.getByLabel("Alter bis")).toHaveValue("18");
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
  // Schnellzugang für die Ausschreibung (ADR 0020)
  const quick = admin.getByRole("region", { name: "Schnellzugang" });
  await expect(quick.getByRole("img", { name: /QR-Code mit dem Link/ })).toBeVisible();
  const code = (await quick.locator(".font-mono").textContent())!.trim();
  expect(code).toMatch(/^[2-9A-HJKMNP-Z]{6}$/);

  // Ein weiterer, schon vergangener Termin; die Übungsleiterin kommt am Termin dazu
  await admin.getByRole("link", { name: "Termin", exact: true }).click();
  await admin.getByLabel("Beginn", { exact: true }).fill(localDateTime(-1, "10:00"));
  await admin.getByLabel("Ende", { exact: true }).fill(localDateTime(-1, "14:00"));
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByText("Termin angelegt. Trag hier die Übungsleiter ein.")).toBeVisible();
  await admin.getByText("Jemanden eintragen oder Rolle ändern").click();
  await admin.getByLabel("Mitglied").selectOption({ label: "Clara Clever" });
  await admin.getByLabel("Rolle").selectOption({ label: "Trainer" });
  await admin.getByRole("button", { name: "Eintragen", exact: true }).click();
  await expect(admin.getByText("Clara Clever ist als Trainer eingetragen.")).toBeVisible();
  await expectNoA11yViolations(admin);
  // Zielgruppen nur für diesen Termin anpassen und wieder zurücknehmen (ADR 0019)
  const targetGroups = await admin.locator("a", { hasText: "Zielgruppen anpassen" }).getAttribute("href");
  await admin.goto(targetGroups!);
  await expect(admin.getByText("Der Termin übernimmt die Zielgruppen der Veranstaltung")).toBeVisible();
  await expectNoA11yViolations(admin);
  await admin.getByRole("button", { name: "Für diesen Termin anpassen" }).click();
  await expect(admin.getByLabel("Bezeichnung")).toHaveValue("Kinder und Jugend");
  await admin.getByLabel("Alter bis").fill("12");
  await expectNoA11yViolations(admin);
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByText("Zielgruppen für diesen Termin gespeichert.")).toBeVisible();
  await expect(admin.getByText("für diesen Termin angepasst")).toBeVisible();
  await admin.goto(targetGroups!);
  await admin.getByLabel("Weitere Aktionen").click();
  await admin.getByRole("button", { name: "Wieder wie die Veranstaltung" }).click();
  await expect(admin.getByText("Der Termin hat wieder die Zielgruppen der Veranstaltung.")).toBeVisible();

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
  // Filter: standardmäßig nur passende Termine
  await parent.locator("summary", { hasText: "Filter" }).click();
  await expect(parent.getByLabel("Nur passende Termine")).toBeChecked();
  await expectNoA11yViolations(parent);
  await parent.getByLabel("Abgesagte ausblenden").check();
  await parent.getByRole("button", { name: "Anzeigen" }).click();
  await expect(parent.getByText("1 aktiv")).toBeVisible();
  // Code von der Ausschreibung: alle Termine der Veranstaltung
  await parent.getByLabel("Code von der Ausschreibung").fill(code.toLowerCase());
  await parent.getByRole("button", { name: "Öffnen" }).click();
  await expect(parent).toHaveURL(/veranstaltung=\d+/);
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
  await trainer.goto("/termine/");
  await trainer.getByRole("link", { name: "Randori-Lehrgang" }).first().click();
  await expect(trainer.getByRole("heading", { name: "Teilnehmer (1)" })).toBeVisible();
  await expect(trainer.getByText("„kommt mit dem Bus“")).toBeVisible();
  await expect(trainer.getByRole("link", { name: PARENT.email })).toBeVisible();
  await expectNoA11yViolations(trainer);
  // Vertretung: Übertragen öffnet die Auswahl, wer übernimmt (ADR 0018)
  await trainer.getByRole("link", { name: "Meinen Platz übertragen" }).click();
  await expect(trainer.getByRole("heading", { level: 1, name: "Übertragen" })).toBeVisible();
  await expect(trainer.getByLabel("Als", { exact: true })).toHaveValue(/\d+/);
  await expectNoA11yViolations(trainer);
  await trainer.getByRole("link", { name: "Abbrechen" }).click();
  await expect(trainer.getByRole("heading", { name: "Teilnehmer (1)" })).toBeVisible();
  // Mitglieder sieht sie sonst nicht
  expect((await trainer.goto("/mitglieder/"))?.status()).toBe(403);
  // „Meine Abrechnung“: offene Termine aller Monate oben unter „Noch bestätigen“
  await trainer.goto("/abrechnung/");
  await expectNoA11yViolations(trainer);
  await trainer.getByRole("region", { name: "Noch bestätigen" }).getByRole("button", { name: /Randori-Lehrgang am .* bestätigen/ }).click();
  await expect(trainer.getByText("Danke, deine Stunden sind bestätigt.")).toBeVisible();
  await expect(trainer.getByRole("region", { name: "Noch bestätigen" })).toHaveCount(0);
  // Im Monat: Dauer sehen, versehentlich bestätigt? Zurücknehmen und erneut bestätigen
  await trainer.goto(billingMonthPath(1));
  await expect(trainer.getByRole("spinbutton", { name: /Minuten für Randori-Lehrgang/ })).toHaveValue("240");
  await trainer.getByRole("button", { name: /Bestätigung für Randori-Lehrgang am .* zurücknehmen/ }).click();
  await expect(trainer.getByText("Die Bestätigung ist zurückgenommen.")).toBeVisible();
  await trainer.getByRole("button", { name: /Randori-Lehrgang am .* bestätigen/ }).click();
  await expect(trainer.getByRole("spinbutton", { name: /Minuten für Randori-Lehrgang/ })).toHaveValue("240");
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
  // Zielgruppe nur für diese Veranstaltung, ohne Vorlage
  await admin.getByRole("button", { name: "Weitere Zielgruppe hinzufügen" }).click();
  await admin.getByLabel("Bezeichnung").fill("Kinder");
  await admin.getByLabel("Alter bis").fill("18");
  await admin.getByLabel("Wiederkehrend").check();
  await expect(admin.getByLabel("Beginn", { exact: true })).toBeHidden();
  await admin.getByLabel("Dienstag").check();
  await admin.getByLabel("Donnerstag").check();
  // Rhythmus: „Alle x Wochen“ (Standard 1) oder „Jeden n-ten im Monat“, je mit eigenem Feld
  await expect(admin.getByLabel("Alle … Wochen")).toHaveValue("1");
  await expect(admin.getByLabel("Welcher im Monat")).toBeHidden();
  await admin.getByLabel("Jeden n-ten im Monat").check();
  await expect(admin.getByLabel("Welcher im Monat")).toBeVisible();
  await expect(admin.getByLabel("Alle … Wochen")).toBeHidden();
  await expectNoA11yViolations(admin);
  await admin.getByLabel("Alle x Wochen").check();
  await admin.getByLabel("Uhrzeit von").fill("17:00");
  await admin.getByLabel("Uhrzeit bis").fill("18:30");
  // Erst ab morgen: ein Termin von heute läge je nach Uhrzeit schon nach dem Anmeldeschluss (2 Std. vorher).
  await admin.getByLabel("Gültig ab").fill(localDateTime(1, "00:00").slice(0, 10));
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

test("Gast meldet sich über den Link an, bestätigt per Mail und sieht seine Anmeldung", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();
  await admin.goto("/veranstaltungen/neu/");
  await admin.getByLabel("Titel").fill("Offener Lehrgang");
  await admin.getByLabel("Art").selectOption({ label: "Lehrgang" });
  await admin.getByLabel("Externe Teilnehmer zulassen").check();
  await admin.getByLabel("Beginn", { exact: true }).fill(localDateTime(7, "10:00"));
  await admin.getByLabel("Ende", { exact: true }).fill(localDateTime(7, "15:00"));
  await admin.getByRole("button", { name: "Speichern" }).click();
  const link = await admin.getByLabel("Anmeldelink für externe Teilnehmer").inputValue();
  await expectNoA11yViolations(admin);
  await admin.context().close();

  const guestContext = await browser.newContext();
  const guest = await guestContext.newPage();
  await guest.goto(new URL(link).pathname);
  await expect(guest.getByRole("heading", { level: 1, name: "Offener Lehrgang" })).toBeVisible();
  await guest.getByLabel("Vorname").fill("Lena");
  await guest.getByLabel("Nachname").fill("Gast");
  await guest.getByLabel("Jahrgang").fill("1995");
  await guest.getByLabel("Geschlecht").selectOption({ label: "weiblich" });
  await guest.getByLabel("Verein").fill("JC Pinneberg");
  await guest.getByLabel("E-Mail").fill(GUEST.email);
  await guest.getByLabel("Telefon für Notfälle").fill("0170 111");
  await guest.getByLabel(/Datenschutzhinweis gelesen/).check();
  await expectNoA11yViolations(guest);
  await guest.getByRole("button", { name: "Anmelden" }).click();
  await expect(guest.getByRole("heading", { name: "Fast geschafft, Lena!" })).toBeVisible();

  const mail = lastMailTo(GUEST.email);
  const page = mail.match(/https?:\/\/\S+\/gast\/[\w-]+\//);
  expect(page).not.toBeNull();
  await guest.goto(new URL(page![0]).pathname);
  await expect(guest.getByText("noch nicht bestätigt")).toBeVisible();
  await expectNoA11yViolations(guest);
  await guest.getByRole("button", { name: "Anmeldung bestätigen" }).click();
  await expect(guest.getByText("Danke! Deine Anmeldung ist bestätigt.")).toBeVisible();
  await expect(guest.getByText("angemeldet", { exact: true })).toBeVisible();
  await expectNoA11yViolations(guest);
  await guestContext.close();
});
