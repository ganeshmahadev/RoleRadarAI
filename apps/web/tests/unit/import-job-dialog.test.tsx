import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ImportJobDialog } from "@/features/jobs/import-job-dialog";

import { makeCompany, makeJob } from "./fixtures";
import { mockFetchJson, renderWithQuery } from "./render";

const API = "http://localhost:8000/api/v1/jobs";

function body(fetchMock: ReturnType<typeof vi.spyOn>, call = -1) {
  const [url, init] = fetchMock.mock.calls.at(call) as [string, RequestInit];
  return { url, json: JSON.parse(String(init.body)) as Record<string, unknown> };
}

describe("ImportJobDialog", () => {
  it("imports a URL for the company in context", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockFetchJson({ outcome: "created", job: makeJob() }));
    renderWithQuery(<ImportJobDialog company={makeCompany()} open onClose={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Import job — 3Shape A/S" })).toBeVisible();
    await userEvent.type(
      screen.getByLabelText(/Original employer or ATS job URL/),
      "https://job-boards.greenhouse.io/examplefintech/jobs/7001001",
    );
    await userEvent.click(screen.getByRole("button", { name: "Import" }));

    expect(await screen.findByText("Imported a new job.")).toBeInTheDocument();
    expect(body(fetchMock)).toEqual({
      url: `${API}/import-url`,
      json: {
        url: "https://job-boards.greenhouse.io/examplefintech/jobs/7001001",
        company_id: "00000000-0000-4000-8000-000000000001",
      },
    });
    expect(screen.getByRole("link", { name: "View job" })).toHaveAttribute(
      "href",
      "/jobs/10000000-0000-4000-8000-000000000001",
    );
  });

  it("switches to manual paste when the page cannot be retrieved", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        mockFetchJson(
          {
            detail: {
              code: "ROBOTS_DISALLOWED",
              message: "careers.example.com does not allow automated retrieval",
              retryable: false,
            },
          },
          422,
        ),
      )
      .mockResolvedValueOnce(
        mockFetchJson({ outcome: "created", job: makeJob({ source_type: "manual" }) }),
      );
    renderWithQuery(<ImportJobDialog open onClose={vi.fn()} />);

    const url = "https://careers.example.com/jobs/9";
    await userEvent.type(screen.getByLabelText(/Original employer or ATS job URL/), url);
    await userEvent.click(screen.getByRole("button", { name: "Import" }));

    expect(await screen.findByText(/does not allow automated retrieval/)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Paste description" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByLabelText(/Original posting URL/)).toHaveValue(url);

    await userEvent.type(screen.getByLabelText(/Job title/), "Data Engineer");
    await userEvent.type(
      screen.getByLabelText(/Job description/),
      "We need a data engineer to build pipelines with Python and dbt for our desk.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Import" }));

    expect(await screen.findByText("Imported a new job.")).toBeInTheDocument();
    expect(body(fetchMock)).toMatchObject({
      url: `${API}/import-text`,
      json: { title: "Data Engineer", source_url: url },
    });
  });

  it("shows EURES and validation errors inline", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson(
        {
          detail: {
            code: "EURES_NOT_ALLOWED",
            message: "EURES vacancy pages cannot be imported.",
            retryable: false,
          },
        },
        422,
      ),
    );
    renderWithQuery(<ImportJobDialog open onClose={vi.fn()} />);
    await userEvent.type(
      screen.getByLabelText(/Original employer or ATS job URL/),
      "https://europa.eu/eures/portal/jv-se/jv-details/1",
    );
    await userEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "EURES vacancy pages cannot be imported.",
    );
    expect(screen.getByRole("tab", { name: "From URL" })).toHaveAttribute("aria-selected", "true");
  });
});

describe("ImportJobDialog refresh timing", () => {
  it("refreshes lists only after the dialog closes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson({ outcome: "created", job: makeJob() }),
    );
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { render } = await import("@testing-library/react");
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const onClose = vi.fn();
    render(
      <QueryClientProvider client={client}>
        <ImportJobDialog company={makeCompany()} open onClose={onClose} />
      </QueryClientProvider>,
    );
    await userEvent.type(
      screen.getByLabelText(/Original employer or ATS job URL/),
      "https://job-boards.greenhouse.io/examplefintech/jobs/7001001",
    );
    await userEvent.click(screen.getByRole("button", { name: "Import" }));
    await screen.findByText("Imported a new job.");
    expect(invalidate).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["eures"] });
    expect(onClose).toHaveBeenCalled();
  });
});
