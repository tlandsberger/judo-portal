import { expect, test } from '@playwright/test';
import { expectNoA11yViolations, login, logout } from './helpers';

test('Abteilungsleiter legt ein Mitglied an und ändert es, Administrator löscht es', async ({
  page,
}) => {
  // Eindeutiger Name, damit wiederholte Läufe gegen dieselbe Datenbank nicht kollidieren.
  const lastName = `Muster${Date.now()}`;

  await login(page, 'abteilungsleiter@test.local');
  await page.getByRole('link', { name: 'Mitglieder' }).click();
  await expect(page.getByRole('heading', { name: 'Mitglieder' })).toBeVisible();
  await expectNoA11yViolations(page);

  await page.getByRole('link', { name: 'Mitglied anlegen' }).click();
  await expect(page.getByRole('heading', { name: 'Mitglied anlegen' })).toBeVisible();

  // Leeres Formular: Fehlermeldungen an den Pflichtfeldern.
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect(page.getByText('Bitte den Vornamen angeben.')).toBeVisible();
  await expect(page.getByText('Bitte das Geschlecht angeben.')).toBeVisible();

  await page.getByLabel('Vorname').fill('Erika');
  await page.getByLabel('Nachname').fill(lastName);
  await page.getByLabel('Geburtsdatum').fill('2012-03-04');
  await page.getByRole('combobox', { name: 'Geschlecht' }).click();
  await page.getByRole('option', { name: 'weiblich' }).click();
  await page.getByLabel('Ort', { exact: true }).fill('Hamburg');
  await page.getByLabel('E-Mail').fill('erika@example.org');
  await expectNoA11yViolations(page);
  await page.getByRole('button', { name: 'Speichern' }).click();

  await expect(page.getByText('Mitglied angelegt.')).toBeVisible();
  await expect(page).toHaveURL(/\/members$/);
  await page.getByLabel('Suchen (Name, Nummer, Ort)').fill(lastName);
  const row = page.getByRole('row', { name: new RegExp(lastName) });
  await expect(row).toContainText('Hamburg');

  await row.getByRole('link').click();
  await expect(page.getByRole('heading', { name: `Erika ${lastName}` })).toBeVisible();
  await page.getByLabel('Ort', { exact: true }).fill('Wedel');
  await page.getByRole('button', { name: 'Speichern' }).click();
  await expect(page.getByText('Änderungen gespeichert.')).toBeVisible();
  await page.getByLabel('Suchen (Name, Nummer, Ort)').fill(lastName);
  await expect(page.getByRole('row', { name: new RegExp(lastName) })).toContainText('Wedel');
  // Löschen ist dem Administrator vorbehalten.
  await page
    .getByRole('row', { name: new RegExp(lastName) })
    .getByRole('link')
    .click();
  await expect(page.getByRole('button', { name: 'Löschen' })).toHaveCount(0);
  await logout(page);

  await login(page, 'admin@test.local');
  await page.goto('/members');
  await page.getByLabel('Suchen (Name, Nummer, Ort)').fill(lastName);
  await page
    .getByRole('row', { name: new RegExp(lastName) })
    .getByRole('link')
    .click();
  await expect(page.getByText('Du kannst die Daten ansehen, aber nicht ändern.')).toBeVisible();
  await expect(page.getByLabel('Ort', { exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Löschen' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Löschen' }).click();
  await expect(page.getByText('Mitglied gelöscht.')).toBeVisible();
  await page.getByLabel('Suchen (Name, Nummer, Ort)').fill(lastName);
  await expect(page.getByText('Keine Mitglieder gefunden.')).toBeVisible();
});

test('Übungsleiter sehen die Mitgliederverwaltung nicht', async ({ page }) => {
  await login(page, 'trainer@test.local');
  await expect(page.getByRole('link', { name: 'Start' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Mitglieder' })).toHaveCount(0);

  await page.goto('/members');
  await expect(page).toHaveURL(/\/home$/);
});
