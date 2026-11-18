import { expect, test } from "@playwright/test";
import { ADMIN_STATE, acceptInvitation, expectNoA11yViolations, setPassword } from "./helpers";

const TRAINER = { email: "dora@test.local", password: "Sicher-Trainer-246" };

/** Tag im Vormonat für Felder vom Typ datetime-local, z. B. „2026-10-10T18:00“. */
function lastMonth(day: number, time: string): string {
  const now = new Date();
  const date = new Date(now.getFullYear(), now.getMonth() - 1, day);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${time}`;
}

function lastMonthLabel(): string {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth() - 1, 1).toLocaleDateString("de-DE", { month: "long", year: "numeric" });
}

test("Übungsleiterin bestätigt und reicht den Vormonat ein, die Abteilungsleitung gibt frei und lädt das PDF", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();

  // Übungsleiterin mit eigenem Mitgliedsprofil
  await admin.goto("/verwaltung/benutzer/einladen/");
  await admin.getByLabel("E-Mail").fill(TRAINER.email);
  await admin.getByLabel("Vorname").fill("Dora");
  await admin.getByLabel("Nachname").fill("Daumen");
  await admin.getByLabel("Übungsleiter").check();
  await admin.getByRole("button", { name: "Einladung senden" }).click();
  const trainerContext = await browser.newContext();
  const trainer = await trainerContext.newPage();
  await acceptInvitation(trainer, TRAINER.email);
  await setPassword(trainer, TRAINER.password);
  await admin.goto("/mitglieder/neu/");
  await admin.getByLabel("Vorname").fill("Dora");
  await admin.getByLabel("Nachname").fill("Daumen");
  await admin.getByLabel("Geburtsdatum").fill("1985-04-12");
  await admin.getByRole("button", { name: "Speichern" }).click();
  await admin.getByLabel("Dora selbst").check();
  await admin.getByLabel("E-Mail").fill(TRAINER.email);
  await admin.getByRole("button", { name: "Zugang geben" }).click();
  await expect(admin.getByText(`Eigenes Profil · ${TRAINER.email}`)).toBeVisible();

  // Stundensatz für Trainer
  await admin.goto("/abrechnung/saetze/");
  await expect(admin.getByText("Trainer: kein Satz").first()).toBeVisible();
  await expectNoA11yViolations(admin);
  await admin.getByRole("link", { name: "Dora Daumen", exact: true }).click();
  await admin.getByLabel("Rolle").selectOption({ label: "Trainer" });
  await admin.getByLabel("Satz (€/Stunde)").fill("15");
  await admin.getByLabel("Gültig ab").fill(lastMonth(1, "00:00").slice(0, 10));
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByText(/Satz für Trainer ab .* gespeichert/)).toBeVisible();
  await expectNoA11yViolations(admin);

  // Training im Vormonat mit Dora als Trainerin
  await admin.goto("/veranstaltungen/neu/");
  await admin.getByLabel("Titel").fill("Techniktraining");
  await admin.getByLabel("Art").selectOption({ label: "Training" });
  await admin.getByLabel("Einmalig").check();
  await admin.getByLabel("Beginn", { exact: true }).fill(lastMonth(10, "18:00"));
  await admin.getByLabel("Ende", { exact: true }).fill(lastMonth(10, "19:30"));
  await admin.getByLabel("Mitglied").selectOption({ label: "Dora Daumen" });
  await admin.getByLabel("Rolle").selectOption({ label: "Trainer" });
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByText("„Techniktraining“ angelegt mit 1 Termin.")).toBeVisible();
  // Ein zweiter Termin, bei dem Dora dann doch nicht dabei war
  await admin.goto("/veranstaltungen/neu/");
  await admin.getByLabel("Titel").fill("Zusatztraining");
  await admin.getByLabel("Art").selectOption({ label: "Training" });
  await admin.getByLabel("Einmalig").check();
  await admin.getByLabel("Beginn", { exact: true }).fill(lastMonth(12, "18:00"));
  await admin.getByLabel("Ende", { exact: true }).fill(lastMonth(12, "19:30"));
  await admin.getByLabel("Mitglied").selectOption({ label: "Dora Daumen" });
  await admin.getByLabel("Rolle").selectOption({ label: "Trainer" });
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByText("„Zusatztraining“ angelegt mit 1 Termin.")).toBeVisible();

  // Dora bestätigt im Vormonat und reicht ein
  const month = lastMonthLabel();
  await trainer.goto("/abrechnung/");
  await expectNoA11yViolations(trainer);
  await trainer.getByRole("link", { name: month }).click();
  await expect(trainer.getByRole("heading", { name: "Nicht bestätigt" })).toBeVisible();
  await trainer.getByRole("button", { name: /Techniktraining am .* bestätigen/ }).click();
  await expect(trainer.getByText("Danke, deine Stunden sind bestätigt.")).toBeVisible();
  await expect(trainer.getByRole("cell", { name: "22,50 €" }).first()).toBeVisible();
  await expectNoA11yViolations(trainer);
  // Beim Zusatztraining war Dora nicht dabei: entfernen
  // „Nicht dabei?“ führt zum Termin; dort Übertragen oder Entfernen (ADR 0018)
  await trainer.getByRole("link", { name: /Nicht dabei\? Zusatztraining/ }).click();
  await expect(trainer.getByRole("heading", { level: 1, name: "Zusatztraining" })).toBeVisible();
  await expect(trainer.getByRole("link", { name: "Meinen Platz übertragen" })).toBeVisible();
  await expect(trainer.getByRole("button", { name: "Hat nicht stattgefunden" })).toBeHidden(); // im Menü
  await expectNoA11yViolations(trainer);
  await trainer.getByRole("button", { name: "Mich entfernen" }).click();
  await expect(trainer.getByText("Du bist als Trainer ausgetragen.")).toBeVisible();
  await trainer.goto("/abrechnung/");
  await trainer.getByRole("link", { name: month }).click();
  await expect(trainer.getByRole("heading", { name: "Nicht bestätigt" })).toHaveCount(0);
  await trainer.getByRole("button", { name: `${month} einreichen` }).click();
  await expect(trainer.getByText(`${month} ist eingereicht.`)).toBeVisible();
  await expect(trainer.getByRole("button", { name: "Ändern" })).toHaveCount(0);

  // Abteilungsleitung prüft und gibt frei
  await admin.goto("/abrechnung/alle/");
  await expect(admin.getByRole("heading", { name: "Zu prüfen" })).toBeVisible();
  await expectNoA11yViolations(admin);
  await admin.getByRole("link", { name: `Dora Daumen · ${month}` }).click();
  await expectNoA11yViolations(admin);
  await admin.getByRole("button", { name: "Freigeben" }).click();
  await expect(admin.getByText("Die Abrechnung von Dora Daumen ist freigegeben.")).toBeVisible();
  const download = admin.waitForEvent("download");
  await admin.getByRole("link", { name: "PDF herunterladen" }).click();
  expect((await download).suggestedFilename()).toMatch(/^abrechnung-\d{4}-\d{2}-daumen\.pdf$/);

  // Dora sieht die Freigabe
  await trainer.reload();
  await expect(trainer.getByText(/Freigegeben von/)).toBeVisible();
  await trainerContext.close();
  await admin.context().close();
});
