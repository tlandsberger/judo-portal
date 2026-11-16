import { defineConfig, devices } from "@playwright/test";

/**
 * E2E-Tests gegen einen laufenden Portal-Container (siehe e2e/README.md).
 * Die Tests laufen im offiziellen Playwright-Image, damit Screenshots lokal und in der CI gleich aussehen.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  globalSetup: "./e2e/global-setup.ts",
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: "disabled" } },
  snapshotPathTemplate: "{testDir}/__screenshots__/{testFilePath}/{arg}{ext}",
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:8000",
    locale: "de-DE",
    timezoneId: "Europe/Berlin",
    // Für Tests gegen einen Stack mit selbst signiertem Zertifikat (z. B. lokaler Traefik)
    ignoreHTTPSErrors: !!process.env.IGNORE_HTTPS_ERRORS,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] }, testIgnore: /hilfe\.spec\.ts/ },
    // Screenshots für die Hilfe: zuletzt, mit den Daten der anderen Tests (e2e/hilfe.spec.ts)
    { name: "hilfe", use: { ...devices["Desktop Chrome"] }, testMatch: /hilfe\.spec\.ts/, dependencies: ["chromium"] },
  ],
});
