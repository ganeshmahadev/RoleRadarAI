import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProfileForm } from "@/features/profile/profile-form";

import { makeProfile } from "./fixtures";
import { mockFetchJson, renderWithQuery } from "./render";

const URL = "http://localhost:8000/api/v1/resumes/30000000-0000-4000-8000-000000000001/profile";

function patchBody(fetchMock: ReturnType<typeof vi.spyOn>) {
  const call = fetchMock.mock.calls.find(
    (args: unknown[]) => (args[1] as RequestInit | undefined)?.method === "PATCH",
  );
  return call
    ? (JSON.parse(String((call[1] as RequestInit).body)) as Record<string, unknown>)
    : null;
}

describe("ProfileForm", () => {
  it("edits and saves the whole profile", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(mockFetchJson(makeProfile()))
      .mockImplementation(async () =>
        mockFetchJson(
          makeProfile({ skills: ["Python", "SQL"], updated_at: "2026-10-02T10:00:00Z" }),
        ),
      );
    renderWithQuery(
      <ProfileForm resumeId="30000000-0000-4000-8000-000000000001" resumeName="Alex CV" />,
    );

    const save = await screen.findByRole("button", { name: "Save profile" });
    expect(save).toBeDisabled(); // nothing changed yet

    await userEvent.type(screen.getByLabelText("Skills", { selector: "input" }), "SQL{Enter}");
    await userEvent.selectOptions(screen.getByLabelText("Remote preference"), "hybrid");
    await userEvent.click(screen.getByRole("button", { name: "Add language" }));
    await userEvent.type(screen.getByLabelText("Language 2"), "Danish");
    await userEvent.selectOptions(screen.getByLabelText("Level for language 2"), "A2");
    await userEvent.click(save);

    await vi.waitFor(() => expect(patchBody(fetchMock)).not.toBeNull());
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe(URL);
    expect(patchBody(fetchMock)).toMatchObject({
      skills: ["Python", "SQL"],
      remote_preference: "hybrid",
      years_experience: 5.5,
      languages: [
        { language: "English", level: "C2" },
        { language: "Danish", level: "A2" },
      ],
    });
  });

  it("validates years of experience before saving", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockFetchJson(makeProfile()));
    renderWithQuery(<ProfileForm resumeId="r" resumeName="Alex CV" />);
    const years = await screen.findByLabelText("Years of experience");
    await userEvent.clear(years);
    await userEvent.type(years, "61");
    expect(screen.getByText(/0 to 60 with at most one decimal/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save profile" })).toBeDisabled();
    await userEvent.clear(years);
    expect(screen.getByRole("button", { name: "Save profile" })).toBeEnabled(); // cleared = null
  });

  it("discards unsaved changes", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockFetchJson(makeProfile()));
    renderWithQuery(<ProfileForm resumeId="r" resumeName="Alex CV" />);
    const skills = await screen.findByRole("list", { name: "Skills" });
    await userEvent.click(within(skills).getByRole("button", { name: "Remove Python" }));
    await userEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(within(screen.getByRole("list", { name: "Skills" })).getByText("Python")).toBeVisible();
  });
});

describe("ProfileForm save feedback", () => {
  it("shows Saved and adopts the server's cleaned values", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(mockFetchJson(makeProfile({ skills: [] })))
      .mockImplementation(async () =>
        mockFetchJson(makeProfile({ skills: ["SQL"], updated_at: "2026-10-02T11:00:00Z" })),
      );
    renderWithQuery(
      <ProfileForm resumeId="30000000-0000-4000-8000-000000000001" resumeName="Alex CV" />,
    );
    await userEvent.type(
      await screen.findByLabelText("Skills", { selector: "input" }),
      "SQL{Enter}",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));
    expect(await screen.findByText("Saved")).toBeVisible();
    expect(screen.getByRole("button", { name: "Save profile" })).toBeDisabled();
  });
});
