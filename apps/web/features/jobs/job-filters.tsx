"use client";

import { useEffect, useId, useState } from "react";

import { inputClass } from "@/components/ui/styles";
import {
  SOURCE_TYPE_LABELS,
  type BlockedMode,
  type JobQuery,
  type JobSort,
  type SourceType,
  type StatusView,
} from "@/lib/api/jobs";

const DEBOUNCE_MS = 250;

interface Props {
  query: JobQuery;
  onQueryChange: (query: JobQuery) => void;
  /** The ranked Matches view always sorts by score. */
  showSort?: boolean;
}

function useDebouncedField(value: string, commit: (value: string) => void) {
  const [draft, setDraft] = useState(value);
  const [synced, setSynced] = useState(value);
  if (value !== synced) {
    setSynced(value);
    setDraft(value);
  }
  useEffect(() => {
    if (draft === value) return;
    const timer = setTimeout(() => commit(draft), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [draft, value, commit]);
  return [draft, setDraft] as const;
}

export function JobFilters({ query, onQueryChange, showSort = true }: Props) {
  const id = useId();
  const change = (patch: Partial<JobQuery>) => onQueryChange({ ...query, ...patch, page: 1 });
  const [q, setQ] = useDebouncedField(query.q, (value) => change({ q: value }));
  const [location, setLocation] = useDebouncedField(query.location, (value) =>
    change({ location: value }),
  );

  return (
    <div className="flex flex-wrap items-end gap-3" role="search">
      <Field id={`${id}-q`} label="Role or company">
        <input
          id={`${id}-q`}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. ML Engineer"
          className={`${inputClass} w-52`}
        />
      </Field>
      <Field id={`${id}-loc`} label="Location or country">
        <input
          id={`${id}-loc`}
          type="search"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="e.g. Copenhagen"
          className={`${inputClass} w-40`}
        />
      </Field>
      <Field id={`${id}-status`} label="Status">
        <select
          id={`${id}-status`}
          value={query.status}
          onChange={(e) => change({ status: e.target.value as StatusView })}
          className={inputClass}
        >
          <option value="active">New and saved</option>
          <option value="SAVED">Saved</option>
          <option value="NEW">New</option>
          <option value="IGNORED">Ignored</option>
          <option value="all">All</option>
        </select>
      </Field>
      <Field id={`${id}-min`} label="Match">
        <select
          id={`${id}-min`}
          value={query.minScore === null ? "" : String(query.minScore)}
          onChange={(e) =>
            change({ minScore: e.target.value === "" ? null : Number(e.target.value) })
          }
          className={inputClass}
        >
          <option value="">Any</option>
          <option value="55">55 or more</option>
          <option value="70">70 or more</option>
          <option value="85">85 or more</option>
        </select>
      </Field>
      <Field id={`${id}-blocked`} label="Blocked jobs">
        <select
          id={`${id}-blocked`}
          value={query.blocked}
          onChange={(e) => change({ blocked: e.target.value as BlockedMode })}
          className={inputClass}
        >
          <option value="last">Rank below others</option>
          <option value="mixed">Rank by score</option>
          <option value="exclude">Hide</option>
        </select>
      </Field>
      <Field id={`${id}-source`} label="Source">
        <select
          id={`${id}-source`}
          value={query.source}
          onChange={(e) => change({ source: e.target.value as SourceType | "" })}
          className={inputClass}
        >
          <option value="">Any</option>
          {Object.entries(SOURCE_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      {showSort && (
        <Field id={`${id}-sort`} label="Sort">
          <select
            id={`${id}-sort`}
            value={query.sort}
            onChange={(e) => change({ sort: e.target.value as JobSort })}
            className={inputClass}
          >
            <option value="match">Match score</option>
            <option value="newest">Newest</option>
            <option value="company">Company</option>
            <option value="title">Title</option>
          </select>
        </Field>
      )}
      <label className="flex h-8 items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={query.siriOnly}
          onChange={(e) => change({ siriOnly: e.target.checked })}
          className="size-4 accent-accent"
        />
        SIRI companies only
      </label>
    </div>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-muted">
        {label}
      </label>
      {children}
    </div>
  );
}
