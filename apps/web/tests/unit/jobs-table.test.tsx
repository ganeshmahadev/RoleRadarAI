import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { JobsTable } from "@/features/jobs/jobs-table";
import { MatchBadge } from "@/features/jobs/match-badge";
import { MATCHES_QUERY } from "@/features/matches/matches-view";

import { makeJob, makeJobItem } from "./fixtures";
import { mockFetchJson, renderWithQuery } from "./render";

describe("MatchBadge", () => {
  it("shows score and category, never a probability", () => {
    render(<MatchBadge item={makeJobItem()} />);
    expect(screen.getByText("90")).toBeInTheDocument();
    expect(screen.getByText("Strong Match")).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("marks outdated, scoring and unscored states", () => {
    const { rerender } = render(<MatchBadge item={makeJobItem({ match_outdated: true })} />);
    expect(screen.getByText("outdated")).toBeInTheDocument();
    rerender(<MatchBadge item={makeJobItem({ match: null, scoring: true })} />);
    expect(screen.getByText("Scoring…")).toBeInTheDocument();
    rerender(<MatchBadge item={makeJobItem({ match: null })} />);
    expect(screen.getByText("Not scored")).toBeInTheDocument();
  });
});

describe("JobsTable (ranked)", () => {
  it("numbers rows, shows gaps and saves / ignores jobs", async () => {
    const blocked = makeJobItem({
      id: "10000000-0000-4000-8000-000000000002",
      title: "Blocked role",
      match: {
        ...makeJobItem().match!,
        overall_score: 92,
        category: "BLOCKED",
        hard_blocker: true,
        missing_requirements: ["Mandatory language"],
        uncertain_requirements: ["Minimum years of experience"],
      },
    });
    const page = { items: [makeJobItem(), blocked], total: 2, page: 1, page_size: 20 };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (_url, init) =>
        init?.method === "PATCH"
          ? mockFetchJson({ ...makeJob(), status: "SAVED" })
          : mockFetchJson(page),
      );
    renderWithQuery(
      <JobsTable
        variant="ranked"
        caption="Ranked"
        query={MATCHES_QUERY}
        onQueryChange={vi.fn()}
        empty="none"
      />,
    );

    await screen.findByRole("rowheader", { name: "Blocked role" });
    const rows = screen.getAllByRole("row");
    expect(within(rows[1]).getByText("1")).toBeInTheDocument();
    expect(within(rows[2]).getByText("2")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Blocked")).toBeInTheDocument();
    expect(within(rows[2]).getByText("✗ Mandatory language")).toBeInTheDocument();
    expect(within(rows[2]).getByText("△ Minimum years of experience")).toBeInTheDocument();
    expect(within(rows[1]).getByText("None stated")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "/jobs?sort=match&blocked=last&page=1&page_size=20&scored=true",
    );

    const patches = () =>
      fetchMock.mock.calls
        .filter(([, init]) => (init as RequestInit | undefined)?.method === "PATCH")
        .map(([url, init]) => [String(url), JSON.parse(String((init as RequestInit).body))]);

    await userEvent.click(screen.getByRole("button", { name: "Save Applied AI Engineer" }));
    await userEvent.click(screen.getByRole("button", { name: "Ignore Blocked role" }));
    await vi.waitFor(() => expect(patches()).toHaveLength(2));
    expect(patches()).toEqual([
      [
        "http://localhost:8000/api/v1/jobs/10000000-0000-4000-8000-000000000001",
        { status: "SAVED" },
      ],
      [
        "http://localhost:8000/api/v1/jobs/10000000-0000-4000-8000-000000000002",
        { status: "IGNORED" },
      ],
    ]);
  });

  it("offers Restore for ignored jobs and shows the empty state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      mockFetchJson({
        items: [makeJobItem({ status: "IGNORED" })],
        total: 1,
        page: 1,
        page_size: 20,
      }),
    );
    renderWithQuery(
      <JobsTable
        variant="jobs"
        caption="Jobs"
        query={MATCHES_QUERY}
        onQueryChange={vi.fn()}
        empty="nothing here"
      />,
    );
    expect(
      await screen.findByRole("button", { name: "Restore Applied AI Engineer" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Save / })).not.toBeInTheDocument();
  });
});
