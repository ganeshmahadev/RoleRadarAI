import path from "node:path";

import { expect, test } from "@playwright/test";

const SAMPLE = path.join(__dirname, "fixtures", "resume-sample.pdf");

test("upload resume, view extracted text, edit profile, survive reload (P2)", async ({ page }) => {
  await page.goto("/settings/profile");
  await expect(page.getByRole("heading", { name: "Profile & resume" })).toBeVisible();

  // Upload the master resume.
  await page.getByLabel(/Resume file/).setInputFiles(SAMPLE);
  await page.getByLabel("Label (optional)").fill("E2E master");
  await page.getByRole("button", { name: "Upload resume" }).click();
  const row = page.getByRole("row", { name: /E2E master/ });
  await expect(row.getByText("Primary")).toBeVisible();

  // Extracted text is visible.
  const text = page.getByRole("region", { name: "Extracted text" }).locator("pre");
  await expect(text).toContainText("Alex Example");
  await expect(text).toContainText("Languages: English (C2), Danish (A2)");

  // Edit the structured profile.
  await page.getByLabel("Target roles", { exact: true }).fill("Machine Learning Engineer");
  await page.keyboard.press("Enter");
  await page.getByLabel("Skills", { exact: true }).fill("Python, PyTorch");
  await page.keyboard.press("Enter");
  await page.getByLabel("Years of experience").fill("5");
  await page.getByLabel("Remote preference").selectOption("hybrid");
  await page.getByRole("button", { name: "Add language" }).click();
  await page.getByLabel("Language 1", { exact: true }).fill("Danish");
  await page.getByLabel("Level for language 1", { exact: true }).selectOption("A2");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByRole("status").getByText("Saved")).toBeVisible();

  // Reload: everything persisted.
  await page.reload();
  await expect(page.getByRole("row", { name: /E2E master/ }).getByText("Primary")).toBeVisible();
  await expect(page.getByRole("list", { name: "Skills" })).toContainText("PyTorch");
  await expect(page.getByRole("list", { name: "Target roles" })).toContainText(
    "Machine Learning Engineer",
  );
  await expect(page.getByLabel("Years of experience")).toHaveValue("5.0");
  await expect(page.getByLabel("Remote preference")).toHaveValue("hybrid");
  await expect(page.getByLabel("Language 1", { exact: true })).toHaveValue("Danish");
});

test("second resume: profile copied, primary switch, delete promotes", async ({ page }) => {
  await page.goto("/settings/profile");
  await page.getByLabel(/Resume file/).setInputFiles(SAMPLE);
  await page.getByLabel("Label (optional)").fill("E2E second");
  await page.getByRole("button", { name: "Upload resume" }).click();

  // The new resume is selected and its profile starts from the primary's entries.
  await expect(page.getByRole("button", { name: "View E2E second" })).toHaveText("Viewing");
  await expect(page.getByRole("list", { name: "Skills" })).toContainText("PyTorch");

  await page.getByRole("button", { name: "Make E2E second the primary resume" }).click();
  await expect(page.getByRole("row", { name: /E2E second/ }).getByText("Primary")).toBeVisible();

  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Delete E2E second" }).click();
  await expect(page.getByRole("row", { name: /E2E second/ })).toHaveCount(0);
  await expect(page.getByRole("row", { name: /E2E master/ }).getByText("Primary")).toBeVisible();
});

test("unsupported files are rejected with a clear message", async ({ page }) => {
  await page.goto("/settings/profile");
  await page.getByLabel(/Resume file/).setInputFiles({
    name: "resume.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("this is not really a pdf"),
  });
  await page.getByRole("button", { name: "Upload resume" }).click();
  // (Next.js renders its own hidden route-announcer alert, so filter by text.)
  await expect(
    page.getByRole("alert").filter({ hasText: "does not match its .pdf extension" }),
  ).toBeVisible();
});
