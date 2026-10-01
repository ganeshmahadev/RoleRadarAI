import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MatchPanel } from "@/features/matches/match-panel";

import { makeMatch } from "./fixtures";
import { mockFetchJson, renderWithQuery } from "./render";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const JOB = "10000000-0000-4000-8000-000000000001";

describe("MatchPanel", () => {
  it("scores an unscored job, polls while running and shows the result", async () => {
    const queued = makeMatch({ status: "QUEUED", overall_score: null, category: null });
    const done = makeMatch();
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(mockFetchJson([])) // latest: none
      .mockResolvedValueOnce(mockFetchJson({ match: queued, cached: false }, 202))
      .mockImplementation(async () => mockFetchJson([done])); // polling
    renderWithQuery(<MatchPanel jobId={JOB} />);

    await userEvent.click(await screen.findByRole("button", { name: "Score against my resume" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Queued for scoring");
    const post = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(post[0]).toBe(`http://localhost:8000/api/v1/jobs/${JOB}/score`);
    expect(post[1].method).toBe("POST");

    expect(await screen.findByText("84", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("Good Match")).toBeInTheDocument();
    expect(screen.getByText("Skills")).toBeInTheDocument();
    expect(screen.getByText("93")).toBeInTheDocument(); // 92.5 rounded
    expect(screen.getByText("n/a")).toBeInTheDocument(); // no must-have stated
    expect(screen.getByText(/not a chance of being hired/)).toBeInTheDocument();
  });

  it("shows a blocker without changing the score", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson([
        makeMatch({
          category: "BLOCKED",
          hard_blocker: true,
          overall_score: 70.4,
          dimensions: { ...makeMatch().dimensions, must_have: 1.2 },
          requirements: [
            {
              key: "language",
              label: "Mandatory language",
              status: "NOT_MET",
              classification: "blocker",
              stated_probability: 0.97,
              met_probability: 0.012,
            },
          ],
          missing_requirements: ["Mandatory language"],
        }),
      ]),
    );
    renderWithQuery(<MatchPanel jobId={JOB} />);
    expect(await screen.findByText("70")).toBeInTheDocument();
    expect(screen.getByText(/Blocked: mandatory language not met/)).toBeInTheDocument();
    const list = screen.getByRole("list");
    expect(within(list).getByText("Mandatory language")).toBeInTheDocument();
    expect(within(list).getByText("Not met (1%)")).toBeInTheDocument();
  });

  it("explains a missing resume and OpenJev being down", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(mockFetchJson([]))
      .mockResolvedValueOnce(
        mockFetchJson(
          { detail: { code: "NO_PRIMARY_RESUME", message: "Upload a resume", retryable: false } },
          409,
        ),
      )
      .mockResolvedValueOnce(
        mockFetchJson(
          {
            detail: {
              code: "DECISION_PROVIDER_UNAVAILABLE",
              message: "not reachable",
              retryable: true,
            },
          },
          503,
        ),
      );
    renderWithQuery(<MatchPanel jobId={JOB} />);
    const button = await screen.findByRole("button", { name: "Score against my resume" });
    await userEvent.click(button);
    expect(await screen.findByRole("link", { name: /Profile & resume/ })).toHaveAttribute(
      "href",
      "/settings/profile",
    );
    await userEvent.click(button);
    expect(await screen.findByText(/OpenJev is not running/)).toBeInTheDocument();
  });

  it("offers a retry after a failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson([
        makeMatch({
          status: "FAILED",
          overall_score: null,
          error_code: "DECISION_PROVIDER_UNAVAILABLE",
          error_message: "OpenJev is not reachable",
        }),
      ]),
    );
    renderWithQuery(<MatchPanel jobId={JOB} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Scoring failed: OpenJev is not reachable",
    );
    expect(screen.getByRole("button", { name: "Score again" })).toBeEnabled();
  });
});
