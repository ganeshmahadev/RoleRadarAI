"use client";

import { useQuery } from "@tanstack/react-query";

import { buttonClass } from "@/components/ui/styles";
import { EuresStatusBadge } from "@/features/companies/eures-status-badge";
import { getNextUnchecked } from "@/lib/api/eures";

import { EuresRowActions } from "./eures-row-actions";

interface Props {
  afterPosition: number | null;
  onAfterPositionChange: (position: number | null) => void;
}

/**
 * The company to review now: the next NOT_CHECKED/OPENED company in SIRI order.
 * Derived from server state, so a browser refresh returns to the same company.
 */
export function CurrentCompany({ afterPosition, onAfterPositionChange }: Props) {
  const {
    data: company,
    isPending,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["eures", "next", afterPosition],
    queryFn: () => getNextUnchecked(afterPosition),
  });

  return (
    <section
      aria-labelledby="current-company-title"
      className="rounded border border-border bg-surface p-4"
    >
      <h2 id="current-company-title" className="text-xs font-medium uppercase text-muted">
        Next unchecked company
      </h2>
      {isPending && <div className="mt-2 h-6 w-64 animate-pulse rounded bg-border" />}
      {isError && (
        <div role="alert" className="mt-2 text-sm">
          <p className="text-danger">Could not load the next company: {error.message}</p>
          <button type="button" className={`${buttonClass} mt-2`} onClick={() => void refetch()}>
            Retry
          </button>
        </div>
      )}
      {!isPending && !isError && company === null && (
        <p className="mt-2 text-sm">Every company has been checked.</p>
      )}
      {company && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-2">
              <span className="text-lg font-semibold">{company.company_name}</span>
              <EuresStatusBadge status={company.eures_status} />
            </p>
            <p className="text-sm text-muted">
              CVR <span className="font-mono">{company.cvr}</span>
              {company.source_position != null && <> · #{company.source_position} in SIRI list</>}
            </p>
            {company.eures_notes && (
              <p className="mt-1 text-sm">
                <span className="text-muted">Note:</span> {company.eures_notes}
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <EuresRowActions key={company.id} company={company} />
            <button
              type="button"
              className={`${buttonClass} h-7 px-2 text-xs`}
              onClick={() => onAfterPositionChange(company.source_position)}
            >
              Skip for now →
            </button>
          </div>
        </div>
      )}
      {afterPosition != null && (
        <button
          type="button"
          onClick={() => onAfterPositionChange(null)}
          className="mt-3 text-xs text-accent hover:underline"
        >
          Back to the first unchecked company
        </button>
      )}
    </section>
  );
}
