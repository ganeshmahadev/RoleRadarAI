"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import {
  DEFAULT_COMPANY_QUERY,
  EURES_STATUSES,
  type CompanyQuery,
  type CompanySort,
  type StatusFilter,
} from "@/lib/api/companies";

const STATUS_FILTERS: readonly string[] = ["all", "unchecked", "checked", ...EURES_STATUSES];
const SORTS: readonly string[] = ["position", "name", "last_checked"];

export function parseCompanyQuery(
  params: URLSearchParams,
  defaults: CompanyQuery = DEFAULT_COMPANY_QUERY,
): CompanyQuery {
  const status = params.get("status") ?? defaults.status;
  const sort = params.get("sort") ?? defaults.sort;
  const page = Number.parseInt(params.get("page") ?? "", 10);
  return {
    ...defaults,
    q: params.get("q") ?? defaults.q,
    status: STATUS_FILTERS.includes(status) ? (status as StatusFilter) : defaults.status,
    siriOnly: params.has("siri") ? params.get("siri") === "1" : defaults.siriOnly,
    sort: SORTS.includes(sort) ? (sort as CompanySort) : defaults.sort,
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

export function serializeCompanyQuery(query: CompanyQuery, defaults = DEFAULT_COMPANY_QUERY) {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.status !== defaults.status) params.set("status", query.status);
  if (query.siriOnly !== defaults.siriOnly) params.set("siri", query.siriOnly ? "1" : "0");
  if (query.sort !== defaults.sort) params.set("sort", query.sort);
  if (query.page > 1) params.set("page", String(query.page));
  return params;
}

/** Company list state lives in the URL so it survives refresh and can be shared. */
export function useCompanyQuery(defaults: CompanyQuery = DEFAULT_COMPANY_QUERY) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const query = useMemo(
    () => parseCompanyQuery(new URLSearchParams(searchParams.toString()), defaults),
    [searchParams, defaults],
  );
  const setQuery = useCallback(
    (next: CompanyQuery) => {
      const qs = serializeCompanyQuery(next, defaults).toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, defaults],
  );
  return [query, setQuery] as const;
}
