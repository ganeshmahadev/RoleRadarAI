import type { Metadata } from "next";

import { DiscoverView } from "@/features/discovery/discover-view";

export const metadata: Metadata = { title: "Discover · RoleRadarAI" };

export default function DiscoverPage() {
  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Discover</h1>
        <p className="text-sm text-muted">
          Search job boards and EURES for your target roles, import the full descriptions and score
          the relevant ones against your resume. For personal, local testing only: searches are slow
          on purpose, and a source that blocks us is skipped, never worked around. Scoring takes
          several minutes per job, so one run scores only the newest few; the rest are scored first
          next time.
        </p>
      </header>
      <DiscoverView />
    </section>
  );
}
