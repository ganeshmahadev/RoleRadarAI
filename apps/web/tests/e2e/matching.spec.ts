import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

const API = "http://localhost:8200/api/v1";
const SAMPLE = path.join(__dirname, "fixtures", "resume-sample.pdf");

test("score a job against the resume and see every dimension (P5)", async ({ page, request }) => {
  // Arrange through the API: a resume and a pasted job.
  const resume = await request.post(`${API}/resumes`, {
    multipart: {
      file: {
        name: "resume-sample.pdf",
        mimeType: "application/pdf",
        buffer: fs.readFileSync(SAMPLE),
      },
      name: "Scoring sample",
    },
  });
  expect(resume.status()).toBe(201);
  const resumeId = (await resume.json()).id as string;
  const imported = await request.post(`${API}/jobs/import-text`, {
    data: {
      title: "Machine Learning Engineer",
      employer_name: "Scoring Test ApS",
      location: "Copenhagen",
      description:
        "We build ML systems with Python and PyTorch. At least 3 years of experience. Fluent Danish is mandatory.",
    },
  });
  const jobId = (await imported.json()).job.id as string;

  try {
    await page.goto(`/jobs/${jobId}`);
    const panel = page.getByRole("region", { name: "Match Score" });
    await expect(panel.getByText("Not scored yet.")).toBeVisible();

    await panel.getByRole("button", { name: "Score against my resume" }).click();
    await expect(panel.getByRole("status")).toContainText(
      /Queued for scoring|Scoring with OpenJev/,
    );

    // Result arrives by polling; blocked on the language, score unchanged.
    await expect(panel.getByText("/ 100")).toBeVisible({ timeout: 15_000 });
    await expect(panel.getByText(/Blocked: mandatory language not met/)).toBeVisible();
    for (const label of [
      "Must-have requirements",
      "Skills",
      "Experience",
      "Role alignment",
      "Seniority",
      "Domain",
      "Education & certification",
    ]) {
      await expect(panel.getByText(label, { exact: true })).toBeVisible();
    }
    await expect(panel.getByText("Not met (2%)")).toBeVisible();
    await expect(panel.getByText("Met (88%)")).toBeVisible();
    await expect(panel.getByText(/not a chance of being hired/)).toBeVisible();

    // Survives a reload, and an identical request is served from the cache.
    await page.reload();
    await expect(panel.getByText(/Blocked: mandatory language not met/)).toBeVisible();
    const again = await request.post(`${API}/jobs/${jobId}/score`, { data: {} });
    expect(again.status()).toBe(200);
    expect((await again.json()).cached).toBe(true);
  } finally {
    await request.delete(`${API}/jobs/${jobId}`);
    await request.delete(`${API}/resumes/${resumeId}`);
  }
});
