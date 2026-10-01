"use client";

import Link from "next/link";

import { JobFilters } from "@/features/jobs/job-filters";
import { JobsTable } from "@/features/jobs/jobs-table";
import { useJobQuery } from "@/features/jobs/use-job-query";
import { DEFAULT_JOB_QUERY, type JobQuery } from "@/lib/api/jobs";
import { CATEGORY_LABELS } from "@/lib/api/matches";

/** Ranked view (PRD §56): the strongest scored jobs, 20 per screen. */
export const MATCHES_QUERY: JobQuery = {
  ...DEFAULT_JOB_QUERY,
  sort: "match",
  scoredOnly: true,
  pageSize: 20,
};

export function MatchesView() {
  const [query, setQuery] = useJobQuery(MATCHES_QUERY);
  return (
    <div className="space-y-4">
      <JobFilters query={query} onQueryChange={setQuery} showSort={false} />
      {query.category && (
        <p className="text-sm">
          Showing only “{CATEGORY_LABELS[query.category] ?? query.category}” ·{" "}
          <button
            type="button"
            className="text-accent hover:underline"
            onClick={() => setQuery({ ...query, category: "", page: 1 })}
          >
            Show all matches
          </button>
        </p>
      )}
      <JobsTable
        variant="ranked"
        caption="Jobs ranked by Match Score"
        query={query}
        onQueryChange={setQuery}
        empty={
          <>
            No scored jobs yet. Open a job from{" "}
            <Link href="/jobs" className="text-accent underline">
              Jobs
            </Link>{" "}
            and choose “Score against my resume”.
          </>
        }
      />
    </div>
  );
}
