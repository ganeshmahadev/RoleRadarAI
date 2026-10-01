"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { ReactNode } from "react";

import { buttonClass } from "@/components/ui/styles";
import { listJobs, SOURCE_TYPE_LABELS, type JobListItem, type JobQuery } from "@/lib/api/jobs";
import { formatDate } from "@/lib/format";

import { JobStatusActions } from "./job-status-actions";
import { MatchBadge } from "./match-badge";

type Variant = "jobs" | "ranked";

interface Props {
  query: JobQuery;
  onQueryChange: (query: JobQuery) => void;
  variant: Variant;
  caption: string;
  empty: ReactNode;
}

const COLUMNS: Record<Variant, string[]> = {
  jobs: ["Role", "Company", "Location", "Source", "Published", "Match", "Actions"],
  ranked: ["#", "Match", "Role", "Company", "Location", "Gaps", "Actions"],
};

const company = (item: JobListItem) => item.company?.company_name ?? item.employer_name;

export function JobsTable({ query, onQueryChange, variant, caption, empty }: Props) {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["jobs", "list", query],
    queryFn: () => listJobs(query),
    placeholderData: keepPreviousData,
    // Keep "Scoring…" rows fresh without manual reloads.
    refetchInterval: (q) => (q.state.data?.items.some((i) => i.scoring) ? 5000 : false),
  });
  const columns = COLUMNS[variant];

  if (isError) {
    return (
      <div role="alert" className="rounded border border-danger/40 p-4 text-sm">
        <p className="font-medium text-danger">Could not load jobs.</p>
        <p className="mt-1 text-muted">{error.message}</p>
        <button type="button" className={`${buttonClass} mt-3`} onClick={() => void refetch()}>
          Retry
        </button>
      </div>
    );
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const offset = data ? (data.page - 1) * data.page_size : 0;

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded border border-border">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-surface text-left text-xs text-muted">
            <tr>
              {columns.map((c) => (
                <th key={c} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isPending
              ? Array.from({ length: 6 }, (_, i) => (
                  <tr key={i} className="border-t border-border" aria-hidden="true">
                    {columns.map((c) => (
                      <td key={c} className="px-3 py-2.5">
                        <div className="h-3 w-3/4 animate-pulse rounded bg-surface" />
                      </td>
                    ))}
                  </tr>
                ))
              : data.items.map((item, index) => (
                  <tr
                    key={item.id}
                    className={`border-t border-border hover:bg-surface/60 ${item.status === "IGNORED" ? "opacity-60" : ""}`}
                  >
                    {variant === "ranked" && (
                      <td className="px-3 py-2 tabular-nums text-muted">{offset + index + 1}</td>
                    )}
                    {variant === "ranked" && (
                      <td className="px-3 py-2">
                        <MatchBadge item={item} />
                      </td>
                    )}
                    <th scope="row" className="px-3 py-2 text-left font-medium">
                      <Link href={`/jobs/${item.id}`} className="hover:underline">
                        {item.title}
                      </Link>
                      {item.source_update_pending && (
                        <span className="ml-2 rounded border border-warning/40 px-1 text-xs font-normal text-warning">
                          Update to review
                        </span>
                      )}
                    </th>
                    <td className="px-3 py-2">
                      {company(item) ?? <span className="text-muted">Unknown</span>}
                    </td>
                    <td className="px-3 py-2">{item.location ?? "—"}</td>
                    {variant === "jobs" ? (
                      <>
                        <td className="whitespace-nowrap px-3 py-2">
                          {SOURCE_TYPE_LABELS[item.source_type]}
                        </td>
                        <td className="whitespace-nowrap px-3 py-2 text-muted">
                          {formatDate(item.published_at)}
                        </td>
                        <td className="px-3 py-2">
                          <MatchBadge item={item} />
                        </td>
                      </>
                    ) : (
                      <td className="px-3 py-2 text-xs">
                        <Gaps item={item} />
                      </td>
                    )}
                    <td className="px-3 py-2">
                      <JobStatusActions jobId={item.id} title={item.title} status={item.status} />
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
        {data && data.items.length === 0 && (
          <div className="px-3 py-8 text-center text-sm text-muted">{empty}</div>
        )}
      </div>

      {data && data.total > data.page_size && (
        <nav aria-label="Pagination" className="flex items-center justify-between text-sm">
          <p className="text-muted" aria-live="polite">
            {offset + 1}–{Math.min(offset + data.page_size, data.total)} of {data.total}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className={buttonClass}
              disabled={data.page <= 1}
              onClick={() => onQueryChange({ ...query, page: data.page - 1 })}
            >
              Previous
            </button>
            <span className="text-muted">
              Page {data.page} of {totalPages}
            </span>
            <button
              type="button"
              className={buttonClass}
              disabled={data.page >= totalPages}
              onClick={() => onQueryChange({ ...query, page: data.page + 1 })}
            >
              Next
            </button>
          </div>
        </nav>
      )}
    </div>
  );
}

function Gaps({ item }: { item: JobListItem }) {
  const missing = item.match?.missing_requirements ?? [];
  const partial = item.match?.uncertain_requirements ?? [];
  if (!missing.length && !partial.length) return <span className="text-muted">None stated</span>;
  return (
    <span className="space-x-2">
      {missing.map((label) => (
        <span key={label} className="text-danger">
          ✗ {label}
        </span>
      ))}
      {partial.map((label) => (
        <span key={label} className="text-warning">
          △ {label}
        </span>
      ))}
    </span>
  );
}
