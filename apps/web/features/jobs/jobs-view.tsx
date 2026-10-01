"use client";

import { useState } from "react";

import { primaryButtonClass } from "@/components/ui/styles";
import { DEFAULT_JOB_QUERY } from "@/lib/api/jobs";

import { BatchPanel } from "@/features/match-runs/batch-panel";

import { ImportJobDialog } from "./import-job-dialog";
import { JobFilters } from "./job-filters";
import { JobsTable } from "./jobs-table";
import { useJobQuery } from "./use-job-query";

export function JobsView() {
  const [query, setQuery] = useJobQuery(DEFAULT_JOB_QUERY);
  const [importing, setImporting] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <JobFilters query={query} onQueryChange={setQuery} />
        <button type="button" className={primaryButtonClass} onClick={() => setImporting(true)}>
          Import vacancy
        </button>
      </div>
      <BatchPanel />
      {query.companyId && (
        <p className="text-sm">
          Showing jobs for one company ·{" "}
          <button
            type="button"
            className="text-accent hover:underline"
            onClick={() => setQuery({ ...query, companyId: "", page: 1 })}
          >
            Show all jobs
          </button>
        </p>
      )}
      <JobsTable
        variant="jobs"
        caption="Imported jobs"
        query={query}
        onQueryChange={setQuery}
        empty="No jobs match these filters. Import a vacancy from its original employer or ATS page."
      />
      {importing && <ImportJobDialog open onClose={() => setImporting(false)} />}
    </div>
  );
}
