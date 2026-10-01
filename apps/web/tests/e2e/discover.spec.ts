import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

const API = "http://localhost:8200/api/v1";
const SAMPLE = path.join(__dirname, "fixtures", "resume-sample.pdf");

test("discover: search boards + EURES, import, score, rank (P14)", async ({ page, request }) => {
  const upload = await request.post(`${API}/resumes`, {
    multipart: {
      file: {
        name: "resume-sample.pdf",
        mimeType: "application/pdf",
        buffer: fs.readFileSync(SAMPLE),
      },
      name: "Discovery sample",
    },
  });
  const resumeId = (await upload.json()).id as string;
  await request.post(`${API}/resumes/${resumeId}/set-primary`);
  await request.patch(`${API}/resumes/${resumeId}/profile`, {
    data: { target_roles: ["Robotics Engineer"] },
  });
  const first = (await (await request.get(`${API}/companies?sort=position&page_size=1`)).json())
    .items[0];

  try {
    await page.goto("/discover");
    await expect(page.getByText(/Searches for Robotics Engineer in Denmark/)).toBeVisible();

    // Settings through the form: fewer results, EURES on, scan one SIRI company.
    await page.getByLabel("Results per board and term").fill("5");
    await page.getByLabel("SIRI companies scanned per run").fill("1");
    await page.getByLabel("Only jobs posted in the last (hours)").fill("720"); // fixture is 11 days old
    await page.getByRole("checkbox", { name: /EURES/ }).check();
    await page.getByRole("button", { name: "Save settings" }).click();
    await expect(page.getByText("Saved")).toBeVisible();

    await page.getByRole("button", { name: "Search now" }).click();
    const panel = page.getByRole("region", { name: "Latest search" });
    await expect(panel.getByRole("heading", { name: "Last search finished" })).toBeVisible({
      timeout: 60_000,
    });

    const table = panel.getByRole("table", { name: "Results per source" });
    await expect(table.getByRole("row", { name: /Indeed Denmark/ })).toContainText("OK");
    await expect(table.getByRole("row", { name: /EURES company scan/ })).toContainText(
      "1 companies",
    );
    // The same vacancy on LinkedIn becomes another source of the Indeed job.
    await expect(table.getByRole("row", { name: /LinkedIn/ })).toContainText(/0\s*1/);

    const newJobs = panel.getByRole("listitem");
    await expect(newJobs.filter({ hasText: "Senior Robotics Engineer" })).toContainText("Scored");
    await expect(newJobs.filter({ hasText: "Lead Robotics Engineer" })).toContainText("Scored");
    await expect(newJobs.filter({ hasText: "Office Manager" })).toContainText("Not scored");
    await expect(newJobs.filter({ hasText: "Senior Computer Vision & AI Engineer" })).toBeVisible();

    await panel.getByRole("link", { name: "See ranked matches" }).click();
    const ranked = page.getByRole("table", { name: "Jobs ranked by Match Score" });
    await expect(ranked.getByRole("rowheader")).toHaveText([
      "Senior Robotics Engineer",
      "Lead Robotics Engineer",
    ]);

    // The scanned company is marked as checked by the scan, and the dashboard reports the run.
    await page.goto(`/companies?q=${encodeURIComponent(first.cvr)}`);
    await expect(page.getByText("by automated scan")).toBeVisible();
    await page.goto("/");
    await expect(page.getByText(/Last search .*: \d+ new jobs, 2 scored\./)).toBeVisible();
  } finally {
    const runs = await (await request.get(`${API}/discovery-runs?limit=1`)).json();
    for (const job of runs[0]?.new_jobs ?? []) await request.delete(`${API}/jobs/${job.id}`);
    await request.post(`${API}/companies/${first.id}/reset-eures`);
    await request.delete(`${API}/resumes/${resumeId}`);
  }
});
