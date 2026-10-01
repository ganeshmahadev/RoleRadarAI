import type { Metadata } from "next";
import { Suspense } from "react";

import { MatchesView } from "@/features/matches/matches-view";

export const metadata: Metadata = { title: "Matches · RoleRadarAI" };

export default function MatchesPage() {
  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Matches</h1>
        <p className="text-sm text-muted">
          Your scored jobs, strongest first. Jobs blocked by a mandatory requirement rank below the
          rest unless you change it. Scores measure fit under your rubric, not the chance of being
          hired.
        </p>
      </header>
      <Suspense fallback={<p className="text-sm text-muted">Loading matches…</p>}>
        <MatchesView />
      </Suspense>
    </section>
  );
}
