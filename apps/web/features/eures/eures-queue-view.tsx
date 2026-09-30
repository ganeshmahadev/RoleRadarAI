"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { CompaniesTable } from "@/features/companies/companies-table";
import { CompanyToolbar } from "@/features/companies/company-toolbar";
import { useCompanyQuery } from "@/features/companies/use-company-query";
import { DEFAULT_COMPANY_QUERY, type CompanyQuery } from "@/lib/api/companies";

import { CurrentCompany } from "./current-company";
import { EuresRowActions } from "./eures-row-actions";
import { QueueStats } from "./queue-stats";

/** Queue defaults to companies that still need a EURES review. */
export const EURES_QUEUE_DEFAULTS: CompanyQuery = { ...DEFAULT_COMPANY_QUERY, status: "unchecked" };

export function EuresQueueView() {
  const [query, setQuery] = useCompanyQuery(EURES_QUEUE_DEFAULTS);
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const rawAfter = Number.parseInt(searchParams.get("after") ?? "", 10);
  const afterPosition = Number.isFinite(rawAfter) && rawAfter >= 0 ? rawAfter : null;

  const setAfterPosition = (position: number | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (position == null) params.delete("after");
    else params.set("after", String(position));
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  return (
    <div className="space-y-5">
      <QueueStats />
      <CurrentCompany afterPosition={afterPosition} onAfterPositionChange={setAfterPosition} />
      <div className="space-y-3">
        <h2 className="text-sm font-semibold">All companies</h2>
        <CompanyToolbar query={query} onQueryChange={setQuery} />
        <CompaniesTable
          caption="EURES discovery queue"
          query={query}
          onQueryChange={setQuery}
          renderActions={(company) => <EuresRowActions company={company} />}
        />
      </div>
    </div>
  );
}
