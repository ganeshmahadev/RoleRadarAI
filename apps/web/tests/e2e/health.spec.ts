import { expect, test } from "@playwright/test";

test("dashboard reaches the backend health endpoint", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("API connected");
});
