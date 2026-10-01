import { expect, test, type Page } from "@playwright/test";

test.beforeEach(async ({ context }) => {
  await context.route("https://europa.eu/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/html", body: "<title>EURES stub</title>" }),
  );
});

const panel = (page: Page) => page.getByRole("region", { name: "Next unchecked company" });
const checked = async (page: Page) =>
  Number(
    await page.locator("dl div").filter({ hasText: "checked" }).first().locator("dd").textContent(),
  );

test("import a vacancy from the EURES queue (P4-010)", async ({ page, context }) => {
  await page.goto("/eures");
  const current = panel(page);
  const name = ((await current.locator("span.text-lg").textContent()) ?? "").trim();
  expect(name).not.toBe("");
  const checkedBefore = await checked(page);

  // Open EURES for the current company, then come back and import the original posting.
  const [eures] = await Promise.all([
    context.waitForEvent("page"),
    current.getByRole("link", { name: `Open EURES search for ${name} (opens in new tab)` }).click(),
  ]);
  await eures.close();
  await current.getByRole("button", { name: `Import a job for ${name}` }).click();
  const dialog = page.getByRole("dialog", { name: `Import job — ${name}` });

  // EURES pages themselves are refused.
  await dialog
    .getByLabel(/Original employer or ATS job URL/)
    .fill("https://europa.eu/eures/portal/jv-se/jv-details/abc123");
  await dialog.getByRole("button", { name: "Import" }).click();
  await expect(dialog.getByRole("alert")).toContainText("EURES vacancy pages cannot be imported");

  // Paste the description from the employer's page instead.
  await dialog.getByRole("tab", { name: "Paste description" }).click();
  await dialog.getByLabel(/Job title/).fill("Machine Learning Engineer");
  await dialog.getByLabel(/Location/).fill("Copenhagen");
  await dialog
    .getByLabel(/Job description/)
    .fill(
      "Build and deploy machine learning models for production systems using Python and PyTorch.",
    );
  await dialog.getByRole("button", { name: "Import" }).click();
  await expect(dialog.getByText("Imported a new job.")).toBeVisible();

  await dialog.getByRole("link", { name: "View job" }).click();
  await expect(page.getByRole("heading", { name: "Machine Learning Engineer" })).toBeVisible();
  await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Pasted manually").first()).toBeVisible();

  // The company is now "Job found" and the queue moved on.
  await page.goto("/eures");
  await expect(panel(page).locator("span.text-lg")).not.toHaveText(name);
  await expect.poll(() => checked(page)).toBe(checkedBefore + 1);

  // Companies with jobs link to their jobs.
  await page.goto("/companies?jobs=1");
  const row = page.getByRole("row", {
    name: new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
  });
  await expect(row.getByText("Job found")).toBeVisible();
  await row.getByRole("link", { name: `View 1 imported job for ${name}` }).click();
  await expect(page).toHaveURL(/\/jobs\?company=/);
  await expect(page.getByRole("rowheader", { name: "Machine Learning Engineer" })).toBeVisible();
});

test("row menu opens as a real popover", async ({ page }) => {
  await page.goto("/eures");
  const current = panel(page);
  const name = ((await current.locator("span.text-lg").textContent()) ?? "").trim();
  await current.getByRole("button", { name: `More actions for ${name}` }).click();
  await expect(page.getByRole("button", { name: "Mark EURES error" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Mark EURES error" })).toBeHidden();
});
