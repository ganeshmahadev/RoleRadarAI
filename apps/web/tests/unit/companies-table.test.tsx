import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CompaniesTable } from "@/features/companies/companies-table";
import { OpenEuresLink } from "@/features/companies/open-eures-link";
import { DEFAULT_COMPANY_QUERY } from "@/lib/api/companies";

import { makeCompany, makePage } from "./fixtures";
import { mockFetchJson, renderWithQuery } from "./render";

function renderTable(onQueryChange = vi.fn()) {
  renderWithQuery(
    <CompaniesTable
      caption="Companies"
      query={DEFAULT_COMPANY_QUERY}
      onQueryChange={onQueryChange}
      renderActions={(company) => <OpenEuresLink company={company} />}
    />,
  );
  return onQueryChange;
}

describe("CompaniesTable", () => {
  it("renders companies with CVR as text, status and EURES link", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson(
        makePage([
          makeCompany(),
          makeCompany({
            id: "00000000-0000-4000-8000-000000000002",
            company_name: "Zero Lead ApS",
            cvr: "00012345",
            eures_status: "CHECKED_NO_JOBS",
            eures_last_checked_at: "2026-10-01T09:30:00Z",
          }),
        ]),
      ),
    );
    renderTable();

    expect(await screen.findByRole("rowheader", { name: "3Shape A/S" })).toBeInTheDocument();
    expect(screen.getByText("00012345")).toBeInTheDocument();
    expect(screen.getByText("No relevant jobs")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Open EURES search for 3Shape A\/S/ });
    expect(link).toHaveAttribute("href", expect.stringContaining("keywordsEverywhere=3Shape"));
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("Showing 1–2 of 2")).toBeInTheDocument();
    expect(screen.getAllByText("0")).toHaveLength(2); // no jobs yet
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/companies?sort=position&page=1&page_size=50",
      expect.anything(),
    );
  });

  it("links the jobs count to the company's jobs", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson(makePage([makeCompany({ jobs_count: 2 })])),
    );
    renderTable();
    expect(
      await screen.findByRole("link", { name: "View 2 imported jobs for 3Shape A/S" }),
    ).toHaveAttribute("href", "/jobs?company=00000000-0000-4000-8000-000000000001");
  });

  it("shows an empty state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockFetchJson(makePage([])));
    renderTable();
    expect(await screen.findByText("No companies match these filters.")).toBeInTheDocument();
  });

  it("shows an error with retry", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(mockFetchJson({ detail: "Database unavailable" }, 503))
      .mockResolvedValueOnce(mockFetchJson(makePage([makeCompany()])));
    renderTable();

    expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("rowheader", { name: "3Shape A/S" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("paginates", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson(makePage([makeCompany()], 982, 1, 50)),
    );
    const onQueryChange = renderTable();

    expect(await screen.findByText("Page 1 of 20")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(onQueryChange).toHaveBeenCalledWith({ ...DEFAULT_COMPANY_QUERY, page: 2 });
  });
});
