import type { Metadata } from "next";
import { Suspense } from "react";

import { CompaniesView } from "@/features/companies/companies-view";

export const metadata: Metadata = { title: "Companies · RoleRadarAI" };

export default function CompaniesPage() {
  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Companies</h1>
        <p className="text-sm text-muted">
          SIRI Fast-track certified companies. Open a company&apos;s EURES search in a new tab and
          record the outcome.
        </p>
      </header>
      <Suspense fallback={<p className="text-sm text-muted">Loading companies…</p>}>
        <CompaniesView />
      </Suspense>
    </section>
  );
}
