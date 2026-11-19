import { expect, test } from "@playwright/test";
// Läuft nach „veranstaltungen“ (Dateiname) und nutzt dessen Kindertraining. Am Ende werden die Herbstferien wieder
// gelöscht, damit die Termine für die Hilfe-Screenshots stattfinden.
import { ADMIN_STATE, expectNoA11yViolations, moreAction } from "./helpers";

function icsDate(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`;
}

/** iCal-Datei wie von schulferien.org: Herbstferien über die nächsten vier Wochen. */
function ferienIcs(): Buffer {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//schulferien.org//iCal Generator//DE",
    "BEGIN:VEVENT",
    "SUMMARY:Herbstferien 2026 Schleswig-Holstein",
    `DTSTART;VALUE=DATE:${icsDate(1)}`,
    `DTEND;VALUE=DATE:${icsDate(29)}`,
    "UID:F_test_herbst@schulferien.org",
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return Buffer.from(lines.join("\r\n"));
}

test("Ferien und Feiertage importieren, am Zeitplan wählen, Termine fallen aus und finden nach dem Löschen wieder statt", async ({ browser }) => {
  const admin = await (await browser.newContext({ storageState: ADMIN_STATE })).newPage();
  await admin.goto("/veranstaltungen/");
  await moreAction(admin, "link", "Ferien und Feiertage");
  await expect(admin.getByRole("heading", { level: 1, name: "Ferien und Feiertage" })).toBeVisible();
  await expectNoA11yViolations(admin);

  // Import mit Vorschau
  await admin.getByRole("link", { name: "Importieren" }).click();
  await admin.getByLabel("iCal-Datei (.ics)").setInputFiles({ name: "ferien.ics", mimeType: "text/calendar", buffer: ferienIcs() });
  await admin.getByRole("button", { name: "Vorschau anzeigen" }).click();
  await expect(admin.getByRole("heading", { name: "Vorschau" })).toBeVisible();
  await expect(admin.getByText(/Herbstferien 2026:/)).toBeVisible();
  await expectNoA11yViolations(admin);
  await admin.getByRole("button", { name: "1 Zeitraum übernehmen" }).click();
  await expect(admin.getByText("1 Zeitraum übernommen.")).toBeVisible();
  await expect(admin.getByRole("heading", { name: "Herbstferien" })).toBeVisible();

  // Am Zeitplan auswählen: die Termine fallen aus
  await admin.goto("/veranstaltungen/");
  await admin.getByRole("link", { name: "Kindertraining" }).click();
  await admin.getByRole("link", { name: "Dienstag 17:00–18:30" }).click();
  await admin.getByLabel("Herbstferien").check();
  await expectNoA11yViolations(admin);
  await admin.getByRole("button", { name: "Speichern" }).click();
  await expect(admin.getByText(/Termine? f(allen|ällt) wegen Ferien und Feiertagen aus\./)).toBeVisible();
  await expect(admin.getByText("Fällt aus in: Herbstferien")).toBeVisible();
  await expect(admin.getByText("fällt aus: Herbstferien").first()).toBeVisible();

  // Herbstferien löschen: alles findet wieder statt
  await admin.goto("/ferien-und-feiertage/");
  await admin.getByRole("button", { name: "Herbstferien komplett löschen" }).click();
  await expect(admin.getByText(/„Herbstferien“ gelöscht\. \d+ Termine? finde[nt] wieder statt\./)).toBeVisible();
  await admin.goto("/veranstaltungen/");
  await admin.getByRole("link", { name: "Kindertraining" }).click();
  await expect(admin.getByText("fällt aus: Herbstferien")).toHaveCount(0);
  await admin.context().close();
});
