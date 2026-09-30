"use client";

import { useEffect, useId, useState } from "react";

import { inputClass } from "@/components/ui/styles";
import {
  EURES_STATUS_LABELS,
  EURES_STATUSES,
  type CompanyQuery,
  type CompanySort,
  type StatusFilter,
} from "@/lib/api/companies";

const SEARCH_DEBOUNCE_MS = 250;

interface Props {
  query: CompanyQuery;
  onQueryChange: (query: CompanyQuery) => void;
}

export function CompanyToolbar({ query, onQueryChange }: Props) {
  const id = useId();
  const [draft, setDraft] = useState(query.q);
  const [syncedQ, setSyncedQ] = useState(query.q);
  if (query.q !== syncedQ) {
    // URL changed from outside (back/forward, reset): adopt it.
    setSyncedQ(query.q);
    setDraft(query.q);
  }

  useEffect(() => {
    if (draft === query.q) return;
    const timer = setTimeout(
      () => onQueryChange({ ...query, q: draft, page: 1 }),
      SEARCH_DEBOUNCE_MS,
    );
    return () => clearTimeout(timer);
  }, [draft, query, onQueryChange]);

  return (
    <div className="flex flex-wrap items-end gap-3" role="search">
      <div className="flex min-w-56 flex-1 flex-col gap-1">
        <label htmlFor={`${id}-q`} className="text-xs font-medium text-muted">
          Search
        </label>
        <input
          id={`${id}-q`}
          type="search"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Company name or CVR"
          className={inputClass}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-status`} className="text-xs font-medium text-muted">
          EURES status
        </label>
        <select
          id={`${id}-status`}
          value={query.status}
          onChange={(event) =>
            onQueryChange({ ...query, status: event.target.value as StatusFilter, page: 1 })
          }
          className={inputClass}
        >
          <option value="all">All</option>
          <option value="unchecked">Unchecked (not checked or opened)</option>
          <option value="checked">Checked (any outcome)</option>
          <optgroup label="Exact status">
            {EURES_STATUSES.map((status) => (
              <option key={status} value={status}>
                {EURES_STATUS_LABELS[status]}
              </option>
            ))}
          </optgroup>
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-sort`} className="text-xs font-medium text-muted">
          Sort
        </label>
        <select
          id={`${id}-sort`}
          value={query.sort}
          onChange={(event) =>
            onQueryChange({ ...query, sort: event.target.value as CompanySort, page: 1 })
          }
          className={inputClass}
        >
          <option value="position">SIRI list order</option>
          <option value="name">Name</option>
          <option value="last_checked">Last checked</option>
        </select>
      </div>
      <label className="flex h-8 items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={query.siriOnly}
          onChange={(event) => onQueryChange({ ...query, siriOnly: event.target.checked, page: 1 })}
          className="size-4 accent-accent"
        />
        SIRI certified only
      </label>
    </div>
  );
}
