import { expect, test } from '@playwright/test';
import { expectNoA11yViolations, login } from './helpers';

test('Abteilungsleiter importiert die Mitgliederliste als CSV', async ({ page }) => {
  // Eindeutige Nummern, damit wiederholte Läufe gegen dieselbe Datenbank neue Mitglieder anlegen.
  const run = Date.now();
  const csv = [
    'Mitgliedsnr;Anrede;Name;Vorname;Geburtsdatum;Telefon privat;E-Mail;Vereinseintritt;Vereinsaustritt',
    `E${run}-1;Frau;Importiert${run};Lena;12.05.2013;040 123;lena@example.org;01.09.2019;`,
    `E${run}-2;;Importiert${run};Jonas;03.02.2011;;;15.01.2018;`,
    `E${run}-3;Herr;Importiert${run};Paul;31.02.2015;;;01.03.2022;`,
  ].join('\r\n');

  await login(page, 'abteilungsleiter@test.local');
  await page.goto('/members');
  await page.getByRole('link', { name: 'Importieren' }).click();
  await expect(page.getByRole('heading', { name: 'Mitglieder importieren' })).toBeVisible();
  await expectNoA11yViolations(page);

  await page.locator('input[type=file]').setInputFiles({
    name: 'mitglieder.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(csv, 'utf-8'),
  });
  await expect(page.getByRole('heading', { name: 'Vorschau' })).toBeVisible();
  await expect(page.getByText('2 neu', { exact: true })).toBeVisible();
  await expect(page.getByText('1 mit Fehlern', { exact: true })).toBeVisible();
  await expect(page.getByText('Geburtsdatum „31.02.2015“ ist kein Datum')).toBeVisible();
  await expect(
    page.getByText('Keine Anrede – Geschlecht bitte im Portal nachtragen.'),
  ).toBeVisible();
  await expectNoA11yViolations(page);

  await page.getByRole('button', { name: 'Import ausführen (2 neu, 0 geändert)' }).click();
  await expect(page.getByText('Import abgeschlossen: 2 neu, 0 aktualisiert.')).toBeVisible();
  await expect(page).toHaveURL(/\/members$/);

  await page.getByLabel('Suchen (Name, Nummer, Ort)').fill(`Importiert${run}`);
  await expect(page.getByText('2 Mitglieder')).toBeVisible();
  await expect(page.getByRole('row', { name: /Jonas/ })).toContainText('Geschlecht fehlt');
});
