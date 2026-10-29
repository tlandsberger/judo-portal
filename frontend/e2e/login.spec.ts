import AxeBuilder from '@axe-core/playwright';
import { expect, Page, test } from '@playwright/test';

async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(results.violations).toEqual([]);
}

test('Login als Übungsleiter zeigt Name und Rollen, Abmelden führt zurück', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Willkommen im Vereinsportal' })).toBeVisible();
  await expectNoA11yViolations(page);

  await page.getByRole('button', { name: 'Anmelden' }).click();

  // Keycloak-Anmeldeseite (Realm judo, Testnutzer aus infra/keycloak/realm-judo-dev.json)
  await page.locator('#username').fill('trainer@test.local');
  await page.locator('#password').fill('test');
  await page.locator('#kc-login').click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByRole('heading', { name: 'Hallo Tom Trainer' })).toBeVisible();
  await expect(page.getByText('trainer@test.local')).toBeVisible();
  const roles = page
    .getByRole('listbox', { name: 'Deine Rollen' })
    .or(page.locator('mat-chip-set'));
  await expect(roles).toContainText('Mitglied');
  await expect(roles).toContainText('Übungsleiter');
  await expectNoA11yViolations(page);

  await page.getByRole('button', { name: 'Abmelden' }).click();
  await expect(page.getByRole('button', { name: 'Anmelden' })).toBeVisible();

  // Nach dem Abmelden ist /home nicht mehr erreichbar.
  await page.goto('/home');
  await expect(page.getByRole('button', { name: 'Anmelden' })).toBeVisible();
});

test('PWA-Manifest und Icons sind erreichbar', async ({ request }) => {
  const manifest = await (await request.get('/manifest.webmanifest')).json();
  expect(manifest.name).toBe('WTSV Judo');
  expect(manifest.theme_color).toBe('#027d31');
  const purposes = manifest.icons.map((icon: { purpose: string }) => icon.purpose);
  expect(purposes).toContain('maskable');
  for (const icon of manifest.icons) {
    expect((await request.get(`/${icon.src}`)).status(), icon.src).toBe(200);
  }
});
