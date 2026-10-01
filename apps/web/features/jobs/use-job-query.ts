"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import {
  DEFAULT_JOB_QUERY,
  SOURCE_TYPE_LABELS,
  type BlockedMode,
  type JobQuery,
  type JobSort,
  type SourceType,
  type StatusView,
} from "@/lib/api/jobs";

const SORTS: readonly string[] = ["match", "newest", "company", "title"];
const BLOCKED: readonly string[] = ["last", "mixed", "exclude"];
const STATUSES: readonly string[] = ["active", "all", "NEW", "SAVED", "IGNORED"];
const CATEGORIES: readonly string[] = ["STRONG", "GOOD", "STRETCH", "LOW", "BLOCKED"];

export function parseJobQuery(params: URLSearchParams, defaults: JobQuery): JobQuery {
  const pick = <T extends string>(key: string, allowed: readonly string[], fallback: T) => {
    const value = params.get(key);
    return value && allowed.includes(value) ? (value as T) : fallback;
  };
  const page = Number.parseInt(params.get("page") ?? "", 10);
  const min = Number.parseFloat(params.get("min") ?? "");
  const source = params.get("source") ?? "";
  return {
    ...defaults,
    q: params.get("q") ?? defaults.q,
    location: params.get("location") ?? defaults.location,
    companyId: params.get("company") ?? defaults.companyId,
    source: source in SOURCE_TYPE_LABELS ? (source as SourceType) : defaults.source,
    status: pick<StatusView>("status", STATUSES, defaults.status),
    siriOnly: params.has("siri") ? params.get("siri") === "1" : defaults.siriOnly,
    scoredOnly: params.has("scored") ? params.get("scored") === "1" : defaults.scoredOnly,
    minScore: Number.isFinite(min) && min >= 0 && min <= 100 ? min : defaults.minScore,
    category: pick<string>("cat", CATEGORIES, defaults.category),
    blocked: pick<BlockedMode>("blocked", BLOCKED, defaults.blocked),
    sort: pick<JobSort>("sort", SORTS, defaults.sort),
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

export function serializeJobQuery(query: JobQuery, defaults: JobQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.location) params.set("location", query.location);
  if (query.companyId) params.set("company", query.companyId);
  if (query.source) params.set("source", query.source);
  if (query.status !== defaults.status) params.set("status", query.status);
  if (query.siriOnly !== defaults.siriOnly) params.set("siri", query.siriOnly ? "1" : "0");
  if (query.scoredOnly !== defaults.scoredOnly) params.set("scored", query.scoredOnly ? "1" : "0");
  if (query.minScore !== defaults.minScore && query.minScore !== null)
    params.set("min", String(query.minScore));
  if (query.category) params.set("cat", query.category);
  if (query.blocked !== defaults.blocked) params.set("blocked", query.blocked);
  if (query.sort !== defaults.sort) params.set("sort", query.sort);
  if (query.page > 1) params.set("page", String(query.page));
  return params;
}

/** Job list state lives in the URL so it survives refresh and can be bookmarked. */
export function useJobQuery(defaults: JobQuery = DEFAULT_JOB_QUERY) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const query = useMemo(
    () => parseJobQuery(new URLSearchParams(searchParams.toString()), defaults),
    [searchParams, defaults],
  );
  const setQuery = useCallback(
    (next: JobQuery) => {
      const qs = serializeJobQuery(next, defaults).toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, defaults],
  );
  return [query, setQuery] as const;
}
