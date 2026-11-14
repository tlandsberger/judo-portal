import { chromium, type FullConfig } from "@playwright/test";
import { ADMIN, ADMIN_STATE, acceptInvitation, setPassword } from "./helpers";

/** Der erste Administrator nimmt seine Einladung an (PORTAL_INITIAL_ADMIN_EMAIL) und setzt ein Passwort. */
export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL;
  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL, locale: "de-DE", ignoreHTTPSErrors: !!process.env.IGNORE_HTTPS_ERRORS });
  await acceptInvitation(page, ADMIN.email);
  await setPassword(page, ADMIN.password);
  await page.context().storageState({ path: ADMIN_STATE });
  await browser.close();
}
