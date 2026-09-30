import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EuresRowActions } from "@/features/eures/eures-row-actions";

import { makeCompany } from "./fixtures";
import { mockFetchJson, renderWithQuery } from "./render";

const API = "http://localhost:8000/api/v1/companies/00000000-0000-4000-8000-000000000001";

function lastCall(fetchMock: ReturnType<typeof vi.spyOn>) {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
  return { url, method: init.method, body: init.body };
}

describe("EuresRowActions", () => {
  it("marks no relevant jobs", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockFetchJson(makeCompany({ eures_status: "CHECKED_NO_JOBS" })));
    renderWithQuery(<EuresRowActions company={makeCompany()} />);

    await userEvent.click(
      screen.getByRole("button", { name: "Mark 3Shape A/S as no relevant jobs" }),
    );
    await vi.waitFor(() =>
      expect(lastCall(fetchMock)).toEqual({
        url: `${API}/mark-no-jobs`,
        method: "POST",
        body: undefined,
      }),
    );
  });

  it("records OPENED when the EURES link is used", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockFetchJson(makeCompany({ eures_status: "OPENED" })));
    renderWithQuery(<EuresRowActions company={makeCompany()} />);

    const link = screen.getByRole("link", { name: /Open EURES search for 3Shape A\/S/ });
    link.addEventListener("click", (event) => event.preventDefault()); // jsdom: no navigation
    await userEvent.click(link);
    await vi.waitFor(() => expect(lastCall(fetchMock).url).toBe(`${API}/eures-opened`));
  });

  it("offers reset instead of completion actions for completed companies", () => {
    renderWithQuery(<EuresRowActions company={makeCompany({ eures_status: "CHECKED_NO_JOBS" })} />);
    expect(screen.getByRole("button", { name: "Reset EURES status for 3Shape A/S" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /no relevant jobs/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Mark EURES error/ })).not.toBeInTheDocument();
  });

  it("saves notes through the dialog", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockFetchJson(makeCompany({ eures_notes: "Only sales roles" })));
    renderWithQuery(<EuresRowActions company={makeCompany()} />);

    await userEvent.click(screen.getByRole("button", { name: "Add notes for 3Shape A/S" }));
    const dialog = screen.getByRole("dialog", { name: "EURES notes — 3Shape A/S" });
    await userEvent.type(
      within(dialog).getByRole("textbox", { name: "Notes" }),
      "Only sales roles",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Save notes" }));

    await vi.waitFor(() =>
      expect(lastCall(fetchMock)).toEqual({
        url: API,
        method: "PATCH",
        body: JSON.stringify({ eures_notes: "Only sales roles" }),
      }),
    );
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows an error when an action fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson({ detail: "Company not found" }, 404),
    );
    renderWithQuery(<EuresRowActions company={makeCompany()} />);
    await userEvent.click(screen.getByRole("button", { name: "Mark EURES error for 3Shape A/S" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Company not found");
  });
});
