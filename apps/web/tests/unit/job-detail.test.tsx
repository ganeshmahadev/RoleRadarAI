import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { JobDetail } from "@/features/jobs/job-detail";

import { makeJob } from "./fixtures";
import { mockFetchJson, renderWithQuery } from "./render";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const pendingJob = makeJob({
  source_update_pending: true,
  sources: [
    ...makeJob().sources,
    {
      id: "20000000-0000-4000-8000-000000000002",
      source_type: "greenhouse",
      source_url: "https://job-boards.greenhouse.io/examplefintech/jobs/7001001",
      final_url: null,
      status: "PENDING",
      content_hash: "def",
      fetched_at: "2026-10-02T10:00:00Z",
      normalized: { title: "Senior Applied AI Engineer", description: "New text" },
    },
  ],
});

describe("JobDetail", () => {
  it("renders the job as plain text with original links", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson(makeJob({ description: "<b>not html</b>" })),
    );
    renderWithQuery(<JobDetail jobId="10000000-0000-4000-8000-000000000001" />);
    expect(await screen.findByRole("heading", { name: "Applied AI Engineer" })).toBeInTheDocument();
    expect(screen.getByText("<b>not html</b>")).toBeInTheDocument(); // never rendered as HTML
    expect(screen.getByRole("link", { name: "Open original job ↗" })).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
  });

  it("accepts a pending source update", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(mockFetchJson(pendingJob))
      .mockImplementation(async () =>
        mockFetchJson(makeJob({ title: "Senior Applied AI Engineer" })),
      );
    renderWithQuery(<JobDetail jobId="10000000-0000-4000-8000-000000000001" />);

    expect(await screen.findByText(/The original posting changed/)).toBeInTheDocument();
    expect(screen.getByText("Senior Applied AI Engineer")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Accept update" }));

    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).endsWith("/sources/20000000-0000-4000-8000-000000000002/accept"),
        ),
      ).toBe(true),
    );
    expect(
      await screen.findByRole("heading", { name: "Senior Applied AI Engineer" }),
    ).toBeInTheDocument();
  });

  it("shows not found", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson({ detail: "Job not found" }, 404),
    );
    renderWithQuery(<JobDetail jobId="missing" />);
    expect(await screen.findByText("This job does not exist.")).toBeInTheDocument();
  });
});
