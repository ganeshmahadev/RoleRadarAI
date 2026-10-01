import fs from "node:fs";
import path from "node:path";

import { expect, test, type APIRequestContext } from "@playwright/test";

const API = "http://localhost:8200/api/v1";
const SAMPLE = path.join(__dirname, "fixtures", "resume-sample.pdf");

async function importJob(request: APIRequestContext, title: string, marker = "") {
  const response = await request.post(`${API}/jobs/import-text`, {
    data: {
      title,
      employer_name: "Batch Test ApS",
      location: "Odense, Denmark",
      description: `Batch fixture for ${title}. Daily work with Python and data. ${marker}`,
    },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).job.id as string;
}

test("batch scoring: relevance filter, live progress, ranked result (P7)", async ({
  page,
  request,
}) => {
  const upload = await request.post(`${API}/resumes`, {
    multipart: {
      file: {
        name: "resume-sample.pdf",
        mimeType: "application/pdf",
        buffer: fs.readFileSync(SAMPLE),
      },
      name: "Batch sample",
    },
  });
  const resumeId = (await upload.json()).id as string;
  await request.post(`${API}/resumes/${resumeId}/set-primary`);
  await request.patch(`${API}/resumes/${resumeId}/profile`, {
    data: { target_roles: ["Machine Learning Engineer"] },
  });
  const ids = [
    await importJob(request, "Senior Machine Learning Engineer", "FAKE_LEVEL=3.6"),
    await importJob(request, "Lead Machine Learning Engineer", "FAKE_LEVEL=2.8"),
    await importJob(request, "Office Manager", "FAKE_LEVEL=4.0"),
  ];

  try {
    await page.goto("/matches");
    await expect(page.getByText("No scored jobs yet.")).toBeVisible();
    await page.getByRole("button", { name: "Score jobs in bulk…" }).click();

    const dialog = page.getByRole("dialog", { name: "Score jobs in the background" });
    await expect(dialog.getByText("Target roles: Machine Learning Engineer")).toBeVisible();
    await expect(
      dialog.getByText(/2 jobs will be scored, 1 skipped as not relevant/),
    ).toBeVisible();
    await dialog.locator("summary", { hasText: "Skipped as not relevant" }).click();
    await expect(dialog.getByRole("listitem").filter({ hasText: "Office Manager" })).toBeVisible();
    await dialog.getByRole("button", { name: "Score 2 jobs" }).click();
    await expect(dialog).toBeHidden();

    // Live progress (SSE), then a summary; the ranked list fills in as jobs finish.
    const batch = page.getByRole("region", { name: "Batch scoring" });
    await expect(batch.getByText(/Batch finished: 2 scored, 1 skipped\./)).toBeVisible({
      timeout: 30_000,
    });
    const table = page.getByRole("table", { name: "Jobs ranked by Match Score" });
    await expect(table.getByRole("rowheader")).toHaveText([
      "Senior Machine Learning Engineer",
      "Lead Machine Learning Engineer",
    ]);
    await expect(
      table.getByRole("row", { name: /Senior Machine Learning Engineer/ }).getByText("90"),
    ).toBeVisible();

    // The irrelevant job was never sent to the model.
    await page.goto("/jobs");
    await expect(
      page.getByRole("row", { name: /Office Manager/ }).getByText("Not scored"),
    ).toBeVisible();

    // Nothing left to score now: the next preview says so.
    await page.getByRole("button", { name: "Dismiss" }).click();
    await page.getByRole("button", { name: "Score jobs in bulk…" }).click();
    await expect(page.getByText(/0 jobs will be scored, 1 skipped as not relevant/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Score 0 jobs" })).toBeDisabled();
  } finally {
    for (const id of ids) await request.delete(`${API}/jobs/${id}`);
    await request.delete(`${API}/resumes/${resumeId}`);
  }
});
