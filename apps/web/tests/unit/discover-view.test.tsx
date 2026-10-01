import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DiscoverView } from "@/features/discovery/discover-view";
import type { DiscoveryRun, DiscoverySettings } from "@/lib/api/discovery";

import { mockFetchJson, renderWithQuery } from "./render";

const SETTINGS: DiscoverySettings = {
  search_terms: [],
  location: "Denmark",
  sites: ["indeed", "linkedin", "google"],
  results_per_site: 25,
  hours_old: 72,
  eures_enabled: false,
  eures_companies_per_run: 120,
  scrape_budget_minutes: 20,
  total_budget_minutes: 60,
  effective_terms: ["Data Scientist"],
  jobspy_enabled: true,
  eures_scraper_enabled: false,
  eures_available: false,
};

const entry = (source: string, extra: object = {}) => ({
  source,
  term: "Data Scientist",
  status: "ok",
  message: null,
  found: 3,
  created: 1,
  attached: 1,
  unchanged: 0,
  skipped: 1,
  linked_siri: 1,
  ...extra,
});

function makeRun(overrides: Partial<DiscoveryRun> = {}): DiscoveryRun {
  return {
    id: "70000000-0000-4000-8000-000000000001",
    trigger: "manual",
    status: "RUNNING",
    phase: "SCORING",
    settings: {},
    sources: [
      entry("indeed"),
      entry("linkedin", { status: "blocked", message: "HTTP 429 Too Many Requests", created: 0 }),
    ],
    new_jobs: [{ id: "job-1", title: "Senior Data Scientist", source: "indeed" }],
    scoring: null,
    error_code: null,
    error_message: null,
    created_at: "2026-10-02T06:00:00Z",
    started_at: "2026-10-02T06:00:01Z",
    scrape_deadline: null,
    deadline: null,
    completed_at: null,
    ...overrides,
  };
}

function mockApi(run: DiscoveryRun | null, settings = SETTINGS) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (url, init) => {
    const path = String(url);
    if (path.endsWith("/discovery/settings") && init?.method === "PUT")
      return mockFetchJson({ ...settings, ...JSON.parse(String(init.body)) });
    if (path.endsWith("/discovery/settings")) return mockFetchJson(settings);
    if (path.endsWith("/discovery-runs?limit=1")) return mockFetchJson(run ? [run] : []);
    if (path.endsWith("/discovery-runs") && init?.method === "POST")
      return mockFetchJson(
        makeRun({ status: "QUEUED", phase: "QUEUED", sources: [], new_jobs: [] }),
        202,
      );
    if (path.endsWith("/cancel")) return mockFetchJson(makeRun({ status: "CANCELLED" }));
    throw new Error(`unexpected ${path}`);
  });
}

afterEach(() => vi.restoreAllMocks());

describe("DiscoverView", () => {
  it("starts a search with the profile's roles", async () => {
    const fetchMock = mockApi(null);
    renderWithQuery(<DiscoverView />);
    expect(await screen.findByText("No searches yet.")).toBeInTheDocument();
    expect(screen.getByText(/Searches for Data Scientist in Denmark/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Search now" }));
    expect(await screen.findByRole("heading", { name: "Search queued" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search running…" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/discovery-runs$/),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("is disabled with a reason when discovery is off", async () => {
    mockApi(null, { ...SETTINGS, jobspy_enabled: false });
    renderWithQuery(<DiscoverView />);
    expect(await screen.findByRole("button", { name: "Search now" })).toBeDisabled();
    expect(screen.getByText(/Automated search is off/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "LinkedIn" })).toBeDisabled();
    expect(screen.getByText(/DISCOVERY_JOBSPY_ENABLED/)).toBeInTheDocument();
  });

  it("shows live progress, blocked sources and scoring results", async () => {
    mockApi(
      makeRun({
        scoring: {
          id: "run-2",
          status: "RUNNING",
          scope: "unscored",
          relevance_filter: true,
          target_roles: ["Data Scientist"],
          counts: { DONE: 1 },
          finished: 1,
          total: 3,
          current_job_id: null,
          current_job_title: null,
          seconds_per_job: 720,
          seconds_remaining: 1440,
          error_code: null,
          error_message: null,
          created_at: "2026-10-02T06:20:00Z",
          started_at: "2026-10-02T06:20:00Z",
          completed_at: null,
          items: [
            {
              job_id: "job-1",
              job_title: "Senior Data Scientist",
              status: "DONE",
              reason: null,
              error_code: null,
              matched_role: "Data Scientist",
              match_id: "m1",
              completed_at: null,
            },
          ],
        },
      }),
    );
    renderWithQuery(<DiscoverView />);
    expect(await screen.findByRole("heading", { name: "Searching" })).toBeInTheDocument();
    expect(screen.getByText(/1 of 3 relevant jobs scored · about 24 min left/)).toBeInTheDocument();
    expect(
      within(screen.getByRole("list", { name: "Phases" })).getByText("Scoring"),
    ).toHaveAttribute("aria-current", "step");
    const table = screen.getByRole("table", { name: "Results per source" });
    const linkedin = within(table).getByRole("row", { name: /LinkedIn/ });
    expect(within(linkedin).getByText("Blocked")).toBeInTheDocument();
    expect(within(linkedin).getByText("HTTP 429 Too Many Requests")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Senior Data Scientist" })).toHaveAttribute(
      "href",
      "/jobs/job-1",
    );
    expect(screen.getByText(/Indeed Denmark · Scored/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See ranked matches" })).toHaveAttribute(
      "href",
      "/matches",
    );

    await userEvent.click(screen.getByRole("button", { name: "Cancel search" }));
    expect(
      await screen.findByRole("heading", { name: "Last search cancelled" }),
    ).toBeInTheDocument();
  });

  it("saves settings and validates numbers", async () => {
    const fetchMock = mockApi(null);
    renderWithQuery(<DiscoverView />);
    const results = await screen.findByLabelText("Results per board and term");
    await userEvent.clear(results);
    await userEvent.type(results, "500");
    expect(screen.getByText("Whole number from 1 to 100.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save settings" })).toBeDisabled();
    await userEvent.clear(results);
    await userEvent.type(results, "10");
    await userEvent.click(screen.getByRole("checkbox", { name: "Google Jobs" }));
    await userEvent.type(screen.getByLabelText("Search terms"), "AI Engineer{Enter}");
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    expect(await screen.findByText("Saved")).toBeInTheDocument();
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({
      search_terms: ["AI Engineer"],
      sites: ["indeed", "linkedin"],
      results_per_site: 10,
    });
  });
});
