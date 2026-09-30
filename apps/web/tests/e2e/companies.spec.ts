import { expect, test } from "@playwright/test";

// Requires the SIRI seed import (982 companies) in the API database.
test("browse, search and open EURES for a SIRI company", async ({ page }) => {
  await page.goto("/companies");
  await expect(page.getByRole("heading", { name: "Companies" })).toBeVisible();
  await expect(page.getByText("Showing 1–50 of 982")).toBeVisible();

  await page.getByRole("searchbox", { name: "Search" }).fill("3Shape");
  await expect(page).toHaveURL(/\?q=3Shape/);
  const row = page.getByRole("row", { name: /3Shape A\/S/ });
  await expect(row).toBeVisible();
  await expect(row.getByText("25553489")).toBeVisible();
  await expect(page.getByText("Showing 1–1 of 1")).toBeVisible();

  const eures = row.getByRole("link", {
    name: "Open EURES search for 3Shape A/S (opens in new tab)",
  });
  await expect(eures).toHaveAttribute("href", /keywordsEverywhere=3Shape\+A%2FS/);
  await expect(eures).toHaveAttribute("target", "_blank");

  // Filters live in the URL and survive a reload.
  await page.reload();
  await expect(page.getByRole("searchbox", { name: "Search" })).toHaveValue("3Shape");
  await expect(page.getByText("Showing 1–1 of 1")).toBeVisible();
});

test("CVR values that are not 8 digits are shown exactly", async ({ page }) => {
  await page.goto("/companies?q=8485085");
  await expect(page.getByRole("row", { name: /ROCHE DIAGNOSTICS A\/S/ })).toContainText("8485085");
});
