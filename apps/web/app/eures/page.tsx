import type { Metadata } from "next";
import { Suspense } from "react";

import { EuresQueueView } from "@/features/eures/eures-queue-view";

export const metadata: Metadata = { title: "EURES queue · RoleRadarAI" };

export default function EuresQueuePage() {
  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">EURES discovery queue</h1>
        <p className="text-sm text-muted">
          Open each company&apos;s EURES search in a new tab, review it there, then record the
          outcome here. RoleRadarAI never reads EURES content.
        </p>
      </header>
      <Suspense fallback={<p className="text-sm text-muted">Loading queue…</p>}>
        <EuresQueueView />
      </Suspense>
    </section>
  );
}
