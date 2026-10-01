import { describe, expect, it } from "vitest";

import { parseJobQuery, serializeJobQuery } from "@/features/jobs/use-job-query";
import { MATCHES_QUERY } from "@/features/matches/matches-view";
import { DEFAULT_JOB_QUERY, toJobApiParams } from "@/lib/api/jobs";

describe("job query", () => {
  it("round-trips through the URL and omits defaults", () => {
    const query = {
      ...DEFAULT_JOB_QUERY,
      q: "ml",
      location: "Copenhagen",
      status: "SAVED" as const,
      siriOnly: true,
      minScore: 70,
      category: "STRONG",
      blocked: "mixed" as const,
      sort: "match" as const,
      page: 2,
    };
    const params = serializeJobQuery(query, DEFAULT_JOB_QUERY);
    expect(parseJobQuery(params, DEFAULT_JOB_QUERY)).toEqual(query);
    expect(serializeJobQuery(DEFAULT_JOB_QUERY, DEFAULT_JOB_QUERY).toString()).toBe("");
    expect(serializeJobQuery(MATCHES_QUERY, MATCHES_QUERY).toString()).toBe("");
  });

  it("ignores invalid URL values", () => {
    const parsed = parseJobQuery(
      new URLSearchParams("sort=x&blocked=y&status=APPLIED&min=500&cat=SUPER&source=nope&page=-1"),
      DEFAULT_JOB_QUERY,
    );
    expect(parsed).toEqual(DEFAULT_JOB_QUERY);
  });

  it("maps to API parameters", () => {
    expect(toJobApiParams(MATCHES_QUERY).toString()).toBe(
      "sort=match&blocked=last&page=1&page_size=20&scored=true",
    );
    const all = toJobApiParams({ ...DEFAULT_JOB_QUERY, status: "all" });
    expect(all.getAll("status")).toEqual(["NEW", "SAVED", "IGNORED"]);
    expect(toJobApiParams({ ...DEFAULT_JOB_QUERY, status: "active" }).has("status")).toBe(false);
  });
});
