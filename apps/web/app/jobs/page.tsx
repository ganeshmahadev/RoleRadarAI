import type { Metadata } from "next";
import { Suspense } from "react";

import { JobsView } from "@/features/jobs/jobs-view";

export const metadata: Metadata = { title: "Jobs · RoleRadarAI" };

export default function JobsPage() {
  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Jobs</h1>
        <p className="text-sm text-muted">
          Vacancies imported from their original employer or ATS source. Matching arrives in a later
          phase.
        </p>
      </header>
      <Suspense fallback={<p className="text-sm text-muted">Loading jobs…</p>}>
        <JobsView />
      </Suspense>
    </section>
  );
}
