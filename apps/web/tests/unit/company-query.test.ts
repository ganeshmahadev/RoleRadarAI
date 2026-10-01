import { describe, expect, it } from "vitest";

import { parseCompanyQuery, serializeCompanyQuery } from "@/features/companies/use-company-query";
import { DEFAULT_COMPANY_QUERY, toApiParams } from "@/lib/api/companies";

describe("company query URL state", () => {
  it("round-trips through the URL", () => {
    const query = {
      ...DEFAULT_COMPANY_QUERY,
      q: "novo",
      status: "checked" as const,
      siriOnly: true,
      hasJobs: true,
      sort: "name" as const,
      page: 4,
    };
    const params = serializeCompanyQuery(query);
    expect(params.toString()).toBe("q=novo&status=checked&siri=1&jobs=1&sort=name&page=4");
    expect(parseCompanyQuery(params)).toEqual(query);
  });

  it("omits defaults and ignores invalid values", () => {
    expect(serializeCompanyQuery(DEFAULT_COMPANY_QUERY).toString()).toBe("");
    expect(parseCompanyQuery(new URLSearchParams("status=bogus&sort=x&page=-2"))).toEqual(
      DEFAULT_COMPANY_QUERY,
    );
  });

  it("maps UI filters to API parameters", () => {
    const api = (status: typeof DEFAULT_COMPANY_QUERY.status) =>
      toApiParams({ ...DEFAULT_COMPANY_QUERY, status }).toString();
    expect(api("unchecked")).toContain("checked=false");
    expect(api("checked")).toContain("checked=true");
    expect(api("OPENED")).toContain("eures_status=OPENED");
    expect(api("all")).not.toContain("checked");
    expect(
      toApiParams({ ...DEFAULT_COMPANY_QUERY, q: "  3Shape ", siriOnly: true }).toString(),
    ).toBe("q=3Shape&siri_certified=true&sort=position&page=1&page_size=50");
  });
});
