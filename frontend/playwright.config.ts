import { defineConfig, devices } from '@playwright/test';

/**
 * E2E-Tests gegen die echte Umgebung: infra/compose.dev.yaml (Postgres + Keycloak) und das Backend
 * müssen laufen. Den Angular-Dev-Server startet Playwright selbst (oder nutzt einen laufenden).
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  fullyParallel: false,
  forbidOnly: !!process.env['CI'],
  reporter: process.env['CI'] ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:4200',
    locale: 'de-DE',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Optional: vorinstalliertes Chromium verwenden (z. B. in Cloud-Sandboxes).
        launchOptions: { executablePath: process.env['PW_CHROMIUM_PATH'] || undefined },
      },
    },
  ],
  webServer: {
    command: 'npm start',
    url: 'http://localhost:4200',
    reuseExistingServer: !process.env['CI'],
    timeout: 120_000,
  },
});
