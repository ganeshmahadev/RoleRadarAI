import { expect, test, type Page } from "@playwright/test";

// Never load EURES from tests: stub the new tab's navigation.
test.beforeEach(async ({ context }) => {
  await context.route("https://europa.eu/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/html", body: "<title>EURES stub</title>" }),
  );
});

const current = (page: Page) => page.getByRole("region", { name: "Next unchecked company" });
const stat = (page: Page, label: string) =>
  page.locator("dl div").filter({ hasText: label }).locator("dd");

test("daily EURES loop: open, mark checked, continue, refresh", async ({ page, context }) => {
  await page.goto("/eures");
  await expect(page.getByRole("heading", { name: "EURES discovery queue" })).toBeVisible();
  await expect(stat(page, "companies")).toHaveText("982");
  await expect(stat(page, "checked")).toHaveText("0");
  await expect(stat(page, "remaining")).toHaveText("982");

  // 1. Start with company 1.
  const panel = current(page);
  await expect(panel.getByText("&TRADITION A/S")).toBeVisible();

  // 2. Open its EURES search in a new tab → status OPENED.
  const [eures] = await Promise.all([
    context.waitForEvent("page"),
    panel.getByRole("link", { name: /Open EURES search for &TRADITION A\/S/ }).click(),
  ]);
  expect(eures.url()).toContain("keywordsEverywhere=%26TRADITION+A%2FS");
  await eures.close();
  await expect(panel.getByText("Opened")).toBeVisible();
  await expect(stat(page, "checked")).toHaveText("0"); // OPENED is not a completed check

  // 3. Mark it completed → queue advances to the next unchecked company.
  await panel.getByRole("button", { name: "Mark &TRADITION A/S as no relevant jobs" }).click();
  await expect(panel.getByText("3Shape A/S")).toBeVisible();
  await expect(stat(page, "checked")).toHaveText("1");
  await expect(stat(page, "remaining")).toHaveText("981");

  // 4. Add a note to the current company.
  await panel.getByRole("button", { name: "More actions for 3Shape A/S" }).click();
  await page.getByRole("button", { name: "Add note" }).click();
  const dialog = page.getByRole("dialog", { name: "EURES notes — 3Shape A/S" });
  await dialog.getByRole("textbox", { name: "Notes" }).fill("Check careers page for ML roles");
  await dialog.getByRole("button", { name: "Save notes" }).click();
  await expect(dialog).toBeHidden();
  await expect(panel.getByText("Check careers page for ML roles")).toBeVisible();

  // 5. Refresh: state is unchanged.
  await page.reload();
  await expect(current(page).getByText("3Shape A/S")).toBeVisible();
  await expect(current(page).getByText("Check careers page for ML roles")).toBeVisible();
  await expect(stat(page, "checked")).toHaveText("1");

  // Completed company shows its outcome in the checked view.
  await page.getByLabel("EURES status").selectOption("checked");
  const row = page.getByRole("row", { name: /&TRADITION A\/S/ });
  await expect(row.getByText("No relevant jobs")).toBeVisible();
  await expect(
    row.getByRole("button", { name: "Reset EURES status for &TRADITION A/S" }),
  ).toBeVisible();
});

test("skip moves to the following unchecked company", async ({ page }) => {
  await page.goto("/eures");
  const panel = current(page);
  const first = (await panel.locator("span.text-lg").textContent()) ?? "";
  await panel.getByRole("button", { name: "Skip for now →" }).click();
  await expect(page).toHaveURL(/after=\d+/);
  await expect(panel.locator("span.text-lg")).not.toHaveText(first);
  await panel.getByRole("button", { name: "Back to the first unchecked company" }).click();
  await expect(panel.locator("span.text-lg")).toHaveText(first);
});
