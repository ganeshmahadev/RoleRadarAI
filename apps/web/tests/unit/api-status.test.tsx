import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiStatus } from "@/features/health/api-status";

import { mockFetchJson, renderWithQuery } from "./render";

describe("ApiStatus", () => {
  it("shows connected when the API health endpoint is ok", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockFetchJson({ status: "ok" }));
    renderWithQuery(<ApiStatus />);
    expect(await screen.findByText("API connected")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/api/v1/health", expect.anything());
  });

  it("shows an error when the API is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    renderWithQuery(<ApiStatus />);
    expect(
      await screen.findByText("API unavailable: Cannot reach the RoleRadarAI API"),
    ).toBeInTheDocument();
  });
});
