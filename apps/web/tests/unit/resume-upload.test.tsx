import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ResumeUpload } from "@/features/profile/resume-upload";

import { makeResume } from "./fixtures";
import { mockFetchJson, renderWithQuery } from "./render";

const pdf = (size = 10) =>
  new File([new Uint8Array(size)], "Alex CV.pdf", { type: "application/pdf" });

describe("ResumeUpload", () => {
  it("uploads as multipart without a JSON content type", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockFetchJson(makeResume(), 201));
    const onUploaded = vi.fn();
    renderWithQuery(<ResumeUpload onUploaded={onUploaded} />);

    await userEvent.upload(screen.getByLabelText(/Resume file/), pdf());
    await userEvent.type(screen.getByLabelText("Label (optional)"), "ML 2026");
    await userEvent.click(screen.getByRole("button", { name: "Upload resume" }));

    await vi.waitFor(() => expect(onUploaded).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/resumes");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("name")).toBe("ML 2026");
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("rejects files over 10 MB before uploading", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    renderWithQuery(<ResumeUpload onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/Resume file/), pdf(10 * 1024 * 1024 + 1));
    expect(screen.getByRole("alert")).toHaveTextContent("larger than 10 MB");
    expect(screen.getByRole("button", { name: "Upload resume" })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the server's extraction error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchJson(
        {
          detail: {
            code: "RESUME_EXTRACTION_FAILED",
            message:
              "No readable text was found. If this is a scanned PDF, upload a text-based version.",
            retryable: false,
          },
        },
        422,
      ),
    );
    renderWithQuery(<ResumeUpload onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/Resume file/), pdf());
    await userEvent.click(screen.getByRole("button", { name: "Upload resume" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("scanned PDF");
  });
});
