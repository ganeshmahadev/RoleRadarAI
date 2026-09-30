"use client";

import { EuresRowActions } from "@/features/eures/eures-row-actions";

import { CompaniesTable } from "./companies-table";
import { CompanyToolbar } from "./company-toolbar";
import { useCompanyQuery } from "./use-company-query";

export function CompaniesView() {
  const [query, setQuery] = useCompanyQuery();
  return (
    <div className="space-y-4">
      <CompanyToolbar query={query} onQueryChange={setQuery} />
      <CompaniesTable
        caption="SIRI Fast-track certified companies"
        query={query}
        onQueryChange={setQuery}
        renderActions={(company) => (
          <>
            <EuresRowActions company={company} />
            {company.careers_url && (
              <a
                href={company.careers_url}
                target="_blank"
                rel="noopener noreferrer"
                className="whitespace-nowrap text-sm text-accent hover:underline"
              >
                Careers page ↗
              </a>
            )}
          </>
        )}
      />
    </div>
  );
}
