import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CompanyToolbar } from "@/features/companies/company-toolbar";
import { DEFAULT_COMPANY_QUERY } from "@/lib/api/companies";

describe("CompanyToolbar", () => {
  it("debounces search and resets to page 1", async () => {
    const onQueryChange = vi.fn();
    render(
      <CompanyToolbar
        query={{ ...DEFAULT_COMPANY_QUERY, page: 3 }}
        onQueryChange={onQueryChange}
      />,
    );
    await userEvent.type(screen.getByRole("searchbox", { name: "Search" }), "lego");
    expect(onQueryChange).not.toHaveBeenCalled();
    await vi.waitFor(() =>
      expect(onQueryChange).toHaveBeenCalledWith({ ...DEFAULT_COMPANY_QUERY, q: "lego", page: 1 }),
    );
    expect(onQueryChange).toHaveBeenCalledTimes(1);
  });

  it("changes status, sort and SIRI filter", async () => {
    const onQueryChange = vi.fn();
    render(<CompanyToolbar query={DEFAULT_COMPANY_QUERY} onQueryChange={onQueryChange} />);

    await userEvent.selectOptions(screen.getByLabelText("EURES status"), "unchecked");
    expect(onQueryChange).toHaveBeenLastCalledWith({
      ...DEFAULT_COMPANY_QUERY,
      status: "unchecked",
    });

    await userEvent.selectOptions(screen.getByLabelText("Sort"), "name");
    expect(onQueryChange).toHaveBeenLastCalledWith({ ...DEFAULT_COMPANY_QUERY, sort: "name" });

    await userEvent.click(screen.getByRole("checkbox", { name: "SIRI certified only" }));
    expect(onQueryChange).toHaveBeenLastCalledWith({ ...DEFAULT_COMPANY_QUERY, siriOnly: true });
  });
});
