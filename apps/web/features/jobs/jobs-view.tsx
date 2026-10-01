"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { buttonClass, inputClass, primaryButtonClass } from "@/components/ui/styles";
import { listJobs, SOURCE_TYPE_LABELS } from "@/lib/api/jobs";
import { formatDate } from "@/lib/format";

import { ImportJobDialog } from "./import-job-dialog";

const COLUMNS = ["Role", "Company", "Location", "Source", "Published", "Imported"];

export function JobsView() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const companyId = searchParams.get("company") ?? undefined;
  const q = searchParams.get("q") ?? "";
  const page = Math.max(1, Number.parseInt(searchParams.get("page") ?? "1", 10) || 1);
  const [importing, setImporting] = useState(false);
  const [draft, setDraft] = useState(q);

  const setParams = (updates: Record<string, string | null>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["jobs", { companyId, q, page }],
    queryFn: () => listJobs({ companyId, q, page }),
    placeholderData: keepPreviousData,
  });
  const companyName = companyId ? data?.items[0]?.company?.company_name : undefined;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <form
          role="search"
          className="flex items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setParams({ q: draft.trim() || null, page: null });
          }}
        >
          <div className="flex flex-col gap-1">
            <label htmlFor="job-search" className="text-xs font-medium text-muted">
              Search
            </label>
            <input
              id="job-search"
              type="search"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Title, employer or location"
              className={`${inputClass} w-72`}
            />
          </div>
          <button type="submit" className={buttonClass}>
            Search
          </button>
        </form>
        <button type="button" className={primaryButtonClass} onClick={() => setImporting(true)}>
          Import vacancy
        </button>
      </div>

      {companyId && (
        <p className="text-sm">
          Showing jobs for <span className="font-medium">{companyName ?? "one company"}</span> ·{" "}
          <button
            type="button"
            className="text-accent hover:underline"
            onClick={() => setParams({ company: null, page: null })}
          >
            Show all jobs
          </button>
        </p>
      )}

      {isError ? (
        <div role="alert" className="rounded border border-danger/40 p-4 text-sm">
          <p className="font-medium text-danger">Could not load jobs.</p>
          <p className="mt-1 text-muted">{error.message}</p>
          <button type="button" className={`${buttonClass} mt-3`} onClick={() => void refetch()}>
            Retry
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto rounded border border-border">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">Imported jobs</caption>
            <thead className="bg-surface text-left text-xs text-muted">
              <tr>
                {COLUMNS.map((c) => (
                  <th key={c} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isPending
                ? Array.from({ length: 5 }, (_, i) => (
                    <tr key={i} className="border-t border-border" aria-hidden="true">
                      {COLUMNS.map((c) => (
                        <td key={c} className="px-3 py-2.5">
                          <div className="h-3 w-3/4 animate-pulse rounded bg-surface" />
                        </td>
                      ))}
                    </tr>
                  ))
                : data.items.map((job) => (
                    <tr key={job.id} className="border-t border-border hover:bg-surface/60">
                      <th scope="row" className="px-3 py-2 text-left font-medium">
                        <Link href={`/jobs/${job.id}`} className="hover:underline">
                          {job.title}
                        </Link>
                        {job.source_update_pending && (
                          <span className="ml-2 rounded border border-warning/40 px-1 text-xs font-normal text-warning">
                            Update to review
                          </span>
                        )}
                      </th>
                      <td className="px-3 py-2">
                        {job.company?.company_name ?? job.employer_name ?? (
                          <span className="text-muted">Unknown</span>
                        )}
                      </td>
                      <td className="px-3 py-2">{job.location ?? "—"}</td>
                      <td className="whitespace-nowrap px-3 py-2">
                        {SOURCE_TYPE_LABELS[job.source_type]}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-muted">
                        {formatDate(job.published_at)}
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-muted">
                        {formatDate(job.created_at)}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
          {data && data.items.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-muted">
              No jobs yet. Import a vacancy from its original employer or ATS page.
            </p>
          )}
        </div>
      )}

      {data && data.total > data.page_size && (
        <nav aria-label="Pagination" className="flex items-center justify-end gap-2 text-sm">
          <button
            type="button"
            className={buttonClass}
            disabled={page <= 1}
            onClick={() => setParams({ page: String(page - 1) })}
          >
            Previous
          </button>
          <span className="text-muted">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            className={buttonClass}
            disabled={page >= totalPages}
            onClick={() => setParams({ page: String(page + 1) })}
          >
            Next
          </button>
        </nav>
      )}

      {importing && <ImportJobDialog open onClose={() => setImporting(false)} />}
    </div>
  );
}
