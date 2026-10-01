import fs from "node:fs";
import path from "node:path";

import { expect, test, type APIRequestContext } from "@playwright/test";

const API = "http://localhost:8200/api/v1";
const SAMPLE = path.join(__dirname, "fixtures", "resume-sample.pdf");

async function importJob(request: APIRequestContext, title: string, marker: string) {
  const response = await request.post(`${API}/jobs/import-text`, {
    data: {
      title,
      employer_name: "Ranking Test ApS",
      location: "Aarhus, Denmark",
      description: `Ranking fixture for ${title}. We build data products with Python. ${marker}`,
    },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).job.id as string;
}

async function scoreAndWait(request: APIRequestContext, jobId: string) {
  const { match } = await (await request.post(`${API}/jobs/${jobId}/score`, { data: {} })).json();
  await expect
    .poll(async () => (await (await request.get(`${API}/matches/${match.id}`)).json()).status, {
      timeout: 20_000,
    })
    .toBe("DONE");
}

test("ranked matches: blocked last, save, ignore, outdated, dashboard (P6)", async ({
  page,
  request,
}) => {
  const resume = await request.post(`${API}/resumes`, {
    multipart: {
      file: {
        name: "resume-sample.pdf",
        mimeType: "application/pdf",
        buffer: fs.readFileSync(SAMPLE),
      },
      name: "Ranking sample",
    },
  });
  const resumeId = (await resume.json()).id as string;
  // Earlier specs may have left another primary resume; scoring uses the primary one.
  expect((await request.post(`${API}/resumes/${resumeId}/set-primary`)).ok()).toBeTruthy();
  const blocked = await importJob(request, "Alpha Blocked Engineer", "FAKE_LEVEL=4.0 FAKE_BLOCK");
  const strong = await importJob(request, "Bravo Strong Engineer", "FAKE_LEVEL=3.6");
  const stretch = await importJob(request, "Charlie Stretch Engineer", "FAKE_LEVEL=2.4");
  const ids = [blocked, strong, stretch];

  try {
    for (const id of ids) await scoreAndWait(request, id);

    // The 20 strongest jobs on one screen; blocked ranks below the others by default.
    await page.goto("/matches");
    const table = page.getByRole("table", { name: "Jobs ranked by Match Score" });
    const roles = table.getByRole("rowheader");
    await expect(roles).toHaveText([
      "Bravo Strong Engineer",
      "Charlie Stretch Engineer",
      "Alpha Blocked Engineer",
    ]);
    const bravo = table.getByRole("row", { name: /Bravo Strong Engineer/ });
    await expect(bravo.getByText("90")).toBeVisible();
    await expect(bravo.getByText("Strong Match")).toBeVisible();
    const alpha = table.getByRole("row", { name: /Alpha Blocked Engineer/ });
    await expect(alpha.getByText("Blocked", { exact: true })).toBeVisible();
    await expect(alpha.getByText("✗ Mandatory language")).toBeVisible();

    // Mixed ranking orders purely by score: the blocked job (≈71; its failed language
    // requirement also lowers must-have) moves above the 60-point stretch job.
    await page.getByLabel("Blocked jobs").selectOption("mixed");
    await expect(roles).toHaveText([
      "Bravo Strong Engineer",
      "Alpha Blocked Engineer",
      "Charlie Stretch Engineer",
    ]);
    await page.getByLabel("Blocked jobs").selectOption("exclude");
    await expect(roles).toHaveCount(2);
    await page.getByLabel("Blocked jobs").selectOption("last");

    // Save one, ignore another.
    await page.getByRole("button", { name: "Save Bravo Strong Engineer" }).click();
    await expect(page.getByRole("button", { name: "Unsave Bravo Strong Engineer" })).toBeVisible();
    await page.getByRole("button", { name: "Ignore Charlie Stretch Engineer" }).click();
    await expect(table.getByRole("row", { name: /Charlie Stretch Engineer/ })).toHaveCount(0);
    await page.getByLabel("Status").selectOption("IGNORED");
    await expect(roles).toHaveText(["Charlie Stretch Engineer"]);
    await page.getByRole("button", { name: "Restore Charlie Stretch Engineer" }).click();
    await expect(roles).toHaveCount(0);
    await page.getByLabel("Status").selectOption("SAVED");
    await expect(roles).toHaveText(["Bravo Strong Engineer"]);

    // Dashboard: counts and top matches from the same data.
    await page.goto("/");
    const tile = (label: string) =>
      page.locator("dl > div").filter({ hasText: label }).locator("dd");
    await expect(tile("Strong matches")).toHaveText("1");
    await expect(tile("Saved jobs")).toHaveText("1");
    await expect(
      page.getByRole("region", { name: "Top matches" }).getByRole("listitem").first(),
    ).toContainText("Bravo Strong Engineer");
    await tile("Strong matches").getByRole("link").click();
    await expect(page).toHaveURL(/\/matches\?cat=STRONG/);
    await expect(page.getByText("Showing only “Strong Match”")).toBeVisible();
    await expect(table.getByRole("rowheader")).toHaveText(["Bravo Strong Engineer"]);

    // Editing the profile marks existing scores as outdated.
    await request.patch(`${API}/resumes/${resumeId}/profile`, { data: { skills: ["Rust"] } });
    await page.goto("/matches");
    await expect(
      table.getByRole("row", { name: /Bravo Strong Engineer/ }).getByText("outdated"),
    ).toBeVisible();
    await page.getByRole("link", { name: "Bravo Strong Engineer" }).click();
    await expect(page.getByRole("note")).toContainText("Outdated");
    await expect(page.getByRole("button", { name: "Score again" })).toBeVisible();
  } finally {
    for (const id of ids) await request.delete(`${API}/jobs/${id}`);
    await request.delete(`${API}/resumes/${resumeId}`);
  }
});
