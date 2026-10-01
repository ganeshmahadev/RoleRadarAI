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
          Vacancies imported from their original employer or ATS source. Open a job to score it
          against your resume; the Matches page ranks scored jobs.
        </p>
      </header>
      <Suspense fallback={<p className="text-sm text-muted">Loading jobs…</p>}>
        <JobsView />
      </Suspense>
    </section>
  );
}
