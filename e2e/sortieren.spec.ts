import { expect, test } from "@playwright/test";
import { ADMIN_STATE } from "./helpers";

// Katalogwerte per Pfeil sortieren. Am Ende steht die Reihenfolge wie vorher.
test.use({ storageState: ADMIN_STATE });

test("Veranstaltungsarten per Pfeil sortieren", async ({ page }) => {
  await page.goto("/veranstaltungsarten/");
  const names = () => page.locator("#h-arten ~ ul > li .list-col-grow > a").allTextContents();
  expect((await names()).slice(0, 2)).toEqual(["Training", "Wettkampf"]);
  await expect(page.getByRole("button", { name: "„Training“ nach oben" })).toBeDisabled();

  await page.getByRole("button", { name: "„Wettkampf“ nach oben" }).click();
  await expect(page.getByText("„Wettkampf“ nach oben verschoben.")).toBeVisible();
  expect((await names()).slice(0, 2)).toEqual(["Wettkampf", "Training"]);

  await page.getByRole("button", { name: "„Wettkampf“ nach unten" }).click();
  expect((await names()).slice(0, 2)).toEqual(["Training", "Wettkampf"]);

  // Im Formular gibt es kein Feld „Reihenfolge“ mehr
  await page.goto("/veranstaltungsarten/neu/");
  await expect(page.getByLabel("Reihenfolge")).toHaveCount(0);
});
