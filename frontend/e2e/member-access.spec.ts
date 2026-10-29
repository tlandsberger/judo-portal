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

test('Abteilungsleiter lädt eine Mutter für ihr Kind ein', async ({ page, request }) => {
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
  await dialog.getByLabel('E-Mail').fill(mother);
  await dialog.getByLabel('Vorname').fill('Maria');
  await dialog.getByLabel('Nachname').fill(child);
  await expectNoA11yViolations(page);
  await dialog.getByRole('button', { name: 'Einladen' }).click();

  await expect(page.getByText(`Einladung an ${mother} gesendet.`)).toBeVisible();
  await expect(page.getByText(`Maria ${child}`)).toBeVisible();
  await expect(page.getByText('Eingeladen')).toBeVisible();
  await expectNoA11yViolations(page);

  expect(await invitationLink(request, mother)).toContain(
    '/realms/judo/login-actions/action-token',
  );
});
