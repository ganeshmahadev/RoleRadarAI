"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { buttonClass } from "@/components/ui/styles";
import { listCompanies, type Company, type CompanyQuery } from "@/lib/api/companies";
import { formatDateTime } from "@/lib/format";

import { EuresStatusBadge } from "./eures-status-badge";

interface Props {
  query: CompanyQuery;
  onQueryChange: (query: CompanyQuery) => void;
  /** Row actions; each feature (Companies, EURES queue) supplies its own. */
  renderActions: (company: Company) => ReactNode;
  caption: string;
}

const COLUMNS = ["Company", "CVR", "SIRI", "EURES status", "Last checked", "Actions"];

export const companiesQueryKey = (query: CompanyQuery) => ["companies", query] as const;

export function CompaniesTable({ query, onQueryChange, renderActions, caption }: Props) {
  const { data, isPending, isError, error, refetch, isFetching } = useQuery({
    queryKey: companiesQueryKey(query),
    queryFn: () => listCompanies(query),
    placeholderData: keepPreviousData,
  });

  if (isError) {
    return (
      <div role="alert" className="rounded border border-danger/40 p-4 text-sm">
        <p className="font-medium text-danger">Could not load companies.</p>
        <p className="mt-1 text-muted">{error.message}</p>
        <button type="button" className={`${buttonClass} mt-3`} onClick={() => void refetch()}>
          Retry
        </button>
      </div>
    );
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const first = data && data.total > 0 ? (data.page - 1) * data.page_size + 1 : 0;
  const last = data ? Math.min(data.page * data.page_size, data.total) : 0;

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded border border-border">
        <table className="w-full border-collapse text-sm" aria-busy={isFetching}>
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-surface text-left text-xs text-muted">
            <tr>
              {COLUMNS.map((column) => (
                <th key={column} scope="col" className="px-3 py-2 font-medium">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isPending
              ? Array.from({ length: 8 }, (_, i) => (
                  <tr key={i} className="border-t border-border" aria-hidden="true">
                    {COLUMNS.map((column) => (
                      <td key={column} className="px-3 py-2.5">
                        <div className="h-3 w-3/4 animate-pulse rounded bg-surface" />
                      </td>
                    ))}
                  </tr>
                ))
              : data.items.map((company) => (
                  <tr key={company.id} className="border-t border-border hover:bg-surface/60">
                    <th scope="row" className="px-3 py-2 text-left font-medium">
                      {company.company_name}
                    </th>
                    <td className="px-3 py-2 font-mono text-xs tabular-nums">{company.cvr}</td>
                    <td className="px-3 py-2">
                      {company.siri_certified ? "Certified" : "Not certified"}
                    </td>
                    <td className="px-3 py-2">
                      <EuresStatusBadge status={company.eures_status} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-muted">
                      {formatDateTime(company.eures_last_checked_at)}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        {renderActions(company)}
                      </div>
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
        {data && data.items.length === 0 && (
          <p className="px-3 py-8 text-center text-sm text-muted">
            No companies match these filters.
          </p>
        )}
      </div>

      {data && data.total > 0 && (
        <nav aria-label="Pagination" className="flex items-center justify-between text-sm">
          <p className="text-muted" aria-live="polite">
            Showing {first}–{last} of {data.total}
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
