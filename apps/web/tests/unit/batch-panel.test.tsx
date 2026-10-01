import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BatchPanel } from "@/features/match-runs/batch-panel";
import { formatDuration, type Run, type RunPlan } from "@/lib/api/match-runs";

import { mockFetchJson, renderWithQuery } from "./render";

function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: "60000000-0000-4000-8000-000000000001",
    status: "RUNNING",
    scope: "unscored_or_outdated",
    relevance_filter: true,
    target_roles: ["Data Scientist"],
    counts: { PENDING: 2, RUNNING: 1, DONE: 1, CACHED: 0, SKIPPED: 1, FAILED: 0 },
    finished: 2,
    total: 5,
    current_job_id: "10000000-0000-4000-8000-000000000001",
    current_job_title: "Senior Data Scientist",
    seconds_per_job: 720,
    seconds_remaining: 2160,
    error_code: null,
    error_message: null,
    created_at: "2026-10-02T10:00:00Z",
    started_at: "2026-10-02T10:00:01Z",
    completed_at: null,
    items: [],
    ...overrides,
  };
}

const PLAN: RunPlan = {
  scope: "unscored_or_outdated",
  relevance_filter: true,
  target_roles: ["Data Scientist"],
  to_score: [
    { job_id: "a", title: "Data Scientist", matched_role: "Data Scientist" },
    { job_id: "b", title: "Senior Data Scientist", matched_role: "Data Scientist" },
  ],
  not_relevant: [{ job_id: "c", title: "Office Manager", matched_role: null }],
  seconds_per_job: 720,
};

describe("formatDuration", () => {
  it("rounds to human estimates", () => {
    expect(formatDuration(null)).toBeNull();
    expect(formatDuration(45)).toBe("about a minute");
    expect(formatDuration(1440)).toBe("about 24 min");
    expect(formatDuration(3 * 3600 + 600)).toBe("about 3 h 10 min");
  });
});

describe("BatchPanel", () => {
  it("previews and starts a batch", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
      const path = String(url);
      if (path.endsWith("/match-runs?limit=1")) return mockFetchJson([]);
      if (path.endsWith("/match-runs/preview")) return mockFetchJson(PLAN);
      if (path.endsWith("/match-runs") && init?.method === "POST")
        return mockFetchJson(makeRun({ status: "QUEUED", finished: 1, total: 3 }), 202);
      throw new Error(`unexpected ${path}`);
    });
    renderWithQuery(<BatchPanel />);

    await userEvent.click(await screen.findByRole("button", { name: "Score jobs in bulk…" }));
    const dialog = screen.getByRole("dialog", { name: "Score jobs in the background" });
    expect(
      await within(dialog).findByText(/will be scored, 1 skipped as not relevant/),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/about 24 min/)).toBeInTheDocument();
    expect(within(dialog).getByText("Target roles: Data Scientist")).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: "Score 2 jobs" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Batch queued · 1 of 3 done");
    const start = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/match-runs") && init?.method === "POST",
    );
    expect(JSON.parse(String(start?.[1]?.body))).toEqual({
      scope: "unscored_or_outdated",
      apply_relevance_filter: true,
    });
  });

  it("shows live progress and cancels", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
      String(url).endsWith("/cancel")
        ? mockFetchJson(makeRun({ status: "CANCELLED" }))
        : mockFetchJson([makeRun()]),
    );
    renderWithQuery(<BatchPanel />);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Scoring in the background · 2 of 5 done · about 36 min left",
    );
    expect(screen.getByRole("progressbar", { name: "Batch progress" })).toHaveAttribute(
      "aria-valuenow",
      "40",
    );
    expect(screen.getByText("Now: Senior Data Scientist")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel batch" }));
    expect(await screen.findByText(/Batch cancelled/)).toBeInTheDocument();
  });

  it("summarises a stopped batch with failed jobs", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson([
        makeRun({
          status: "FAILED",
          counts: { PENDING: 0, RUNNING: 0, DONE: 2, CACHED: 1, SKIPPED: 2, FAILED: 1 },
          error_message: "OpenJev is not reachable",
          items: [
            {
              job_id: "x",
              job_title: "Data Scientist",
              status: "FAILED",
              reason: "OpenJev is not reachable",
              error_code: "DECISION_PROVIDER_UNAVAILABLE",
              matched_role: "Data Scientist",
              match_id: null,
              completed_at: null,
            },
          ],
        }),
      ]),
    );
    renderWithQuery(<BatchPanel />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Batch stopped: 2 scored, 1 already up to date, 2 skipped, 1 failed.",
    );
    expect(within(alert).getByText("Data Scientist: OpenJev is not reachable")).toBeInTheDocument();
    await userEvent.click(within(alert).getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Score jobs in bulk…" })).toBeInTheDocument();
  });
});
