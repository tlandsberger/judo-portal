import AxeBuilder from '@axe-core/playwright';
import { expect, Page } from '@playwright/test';

/** Barrierefreiheit nach WCAG 2 A/AA. */
export async function expectNoA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(results.violations).toEqual([]);
}

/** Anmeldung über die Keycloak-Seite mit einem Testnutzer (Passwort `test`). */
export async function login(page: Page, username: string) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Anmelden' }).click();
  await page.locator('#username').fill(username);
  await page.locator('#password').fill('test');
  await page.locator('#kc-login').click();
  await expect(page).toHaveURL(/\/home$/);
}

export async function logout(page: Page) {
  await page.getByRole('button', { name: 'Abmelden' }).click();
  await expect(page.getByRole('button', { name: 'Anmelden' })).toBeVisible();
}
