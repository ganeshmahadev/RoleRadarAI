import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CurrentCompany } from "@/features/eures/current-company";

import { makeCompany } from "./fixtures";
import { mockFetchJson, renderWithQuery } from "./render";

describe("CurrentCompany", () => {
  it("shows the next unchecked company and can skip it", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockFetchJson(makeCompany({ eures_notes: "Try again Monday" })));
    const onAfter = vi.fn();
    renderWithQuery(<CurrentCompany afterPosition={1} onAfterPositionChange={onAfter} />);

    expect(await screen.findByText("3Shape A/S")).toBeInTheDocument();
    expect(screen.getByText("Try again Monday")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/api/v1/eures/next-unchecked?after_position=1",
    );

    await userEvent.click(screen.getByRole("button", { name: "Skip for now →" }));
    expect(onAfter).toHaveBeenCalledWith(2);
    await userEvent.click(
      screen.getByRole("button", { name: "Back to the first unchecked company" }),
    );
    expect(onAfter).toHaveBeenLastCalledWith(null);
  });

  it("reports when every company is checked", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson({ detail: "All companies have been checked" }, 404),
    );
    renderWithQuery(<CurrentCompany afterPosition={null} onAfterPositionChange={vi.fn()} />);
    expect(await screen.findByText("Every company has been checked.")).toBeInTheDocument();
  });

  it("shows errors other than 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockFetchJson({ detail: "Boom" }, 500));
    renderWithQuery(<CurrentCompany afterPosition={null} onAfterPositionChange={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Boom");
  });
});
