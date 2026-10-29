import { expect, test } from '@playwright/test';
import { expectNoA11yViolations, login } from './helpers';

const MAILPIT = process.env['MAILPIT_URL'] ?? 'http://localhost:8025';

/** Wartet auf die Einladungs-Mail in Mailpit (infra/compose.dev.yaml) und liefert den Link darin. */
async function invitationLink(
  request: import('@playwright/test').APIRequestContext,
  to: string,
): Promise<string> {
  for (let attempt = 0; attempt < 20; attempt++) {
    const search = await (
      await request.get(`${MAILPIT}/api/v1/search`, { params: { query: `to:"${to}"` } })
    ).json();
    if (search.messages?.length) {
      const message = await (
        await request.get(`${MAILPIT}/api/v1/message/${search.messages[0].ID}`)
      ).json();
      const link = (message.Text as string).match(/https?:\/\/\S+action-token\S+/)?.[0];
      if (link) {
        return link;
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Keine Einladung an ${to} angekommen`);
}

test('Mutter wird eingeladen, setzt ihr Passwort und sieht ihr Kind schreibgeschützt', async ({
  page,
  request,
}) => {
  const run = Date.now();
  const mother = `mutter-${run}@example.org`;
  const child = `Kind${run}`;

  await login(page, 'abteilungsleiter@test.local');
  await page.goto('/members/new');
  await page.getByLabel('Vorname').fill('Emma');
  await page.getByLabel('Nachname').fill(child);
  await page.getByLabel('Geburtsdatum').fill('2017-06-01');
  await page.getByRole('combobox', { name: 'Geschlecht' }).click();
  await page.getByRole('option', { name: 'weiblich' }).click();
  await page.getByRole('button', { name: 'Speichern' }).click();
  await page.getByLabel('Suchen (Name, Nummer, Ort)').fill(child);
  await page
    .getByRole('row', { name: new RegExp(child) })
    .getByRole('link')
    .click();

  await expect(page.getByRole('heading', { name: 'Zugänge zum Portal' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Eigenen Zugang einladen' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Erziehungsberechtigte einladen' }).click();
  const dialog = page.getByRole('dialog');
  // Der Dialog fokussiert nach dem Öffnen das erste Feld; vorher tippen würde dort landen.
  await expect(dialog.getByLabel('E-Mail')).toBeFocused();
  await dialog.getByLabel('E-Mail').fill(mother);
  await dialog.getByLabel('Vorname').fill('Maria');
  await dialog.getByLabel('Nachname').fill(child);
  await expectNoA11yViolations(page);
  await dialog.getByRole('button', { name: 'Einladen' }).click();

  await expect(page.getByText(`Einladung an ${mother} gesendet.`)).toBeVisible();
  await expect(page.getByText(`Maria ${child}`)).toBeVisible();
  await expect(page.getByText('Eingeladen')).toBeVisible();
  await expectNoA11yViolations(page);

  const link = await invitationLink(request, mother);
  await page.getByRole('button', { name: 'Abmelden' }).click();
  await expect(page.getByRole('button', { name: 'Anmelden' })).toBeVisible();

  // Die Mutter öffnet den Link aus der Mail und legt ihr Passwort fest (Keycloak-Seite).
  await page.goto(link);
  // Keycloak fasst die Aktionen erst zusammen („Klicken Sie hier um fortzufahren“).
  await page.getByRole('link', { name: /fortzufahren|proceed/i }).click();
  await page.locator('#password-new').fill('Sicher-123');
  await page.locator('#password-confirm').fill('Sicher-123');
  await page.locator('[type=submit]').click();
  await expect(page.getByText(/Konto wurde aktualisiert|account has been updated/i)).toBeVisible();

  // Anmelden im Portal; ist die Keycloak-Sitzung schon da, geht es ohne Passwort weiter.
  await page.goto('/');
  await page.getByRole('button', { name: 'Anmelden' }).click();
  const username = page.locator('#username');
  await expect(username.or(page.getByRole('heading', { name: /Hallo/ }))).toBeVisible();
  if (await username.isVisible()) {
    await username.fill(mother);
    await page.locator('#password').fill('Sicher-123');
    await page.locator('#kc-login').click();
  }
  await expect(page.getByRole('heading', { name: `Hallo Maria ${child}` })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Mein Kind' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Mitglieder' })).toHaveCount(0);
  await expectNoA11yViolations(page);

  await page.getByRole('link', { name: 'Daten von Emma ansehen' }).click();
  await expect(page.getByRole('heading', { name: `Emma ${child}` })).toBeVisible();
  await expect(page.getByText('01.06.2017')).toBeVisible();
  await expect(page.locator('input')).toHaveCount(0);
  await expectNoA11yViolations(page);
});
