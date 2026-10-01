"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { isRunActive, latestRun, runEventsUrl, runSchema, type Run } from "@/lib/api/match-runs";

export const LATEST_RUN_KEY = ["match-runs", "latest"] as const;
const POLL_MS = 4000;

/**
 * Latest batch run, kept live through Server-Sent Events (PRD §44), with polling as the
 * fallback when EventSource is unavailable or the stream drops. Job lists refresh whenever
 * another job finishes so scores appear as they arrive.
 */
export function useLatestRun() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: LATEST_RUN_KEY,
    queryFn: latestRun,
    refetchInterval: (q) => {
      const run = q.state.data;
      const streaming = typeof window !== "undefined" && "EventSource" in window;
      return run && isRunActive(run.status) && !streaming ? POLL_MS : false;
    },
  });
  const run = query.data;
  const finished = useRef<number | null>(null);

  useEffect(() => {
    if (run && finished.current !== null && run.finished !== finished.current) {
      void client.invalidateQueries({ queryKey: ["jobs"] });
    }
    finished.current = run?.finished ?? null;
  }, [run, client]);

  const activeId = run && isRunActive(run.status) ? run.id : null;
  useEffect(() => {
    if (!activeId || typeof window === "undefined" || !("EventSource" in window)) return;
    const source = new EventSource(runEventsUrl(activeId));
    source.addEventListener("progress", (event) => {
      const parsed = runSchema.safeParse(JSON.parse((event as MessageEvent<string>).data));
      if (parsed.success) client.setQueryData<Run | null>(LATEST_RUN_KEY, parsed.data);
    });
    source.addEventListener("end", () => source.close());
    // On error EventSource retries by itself; also refresh once so the UI never goes stale.
    source.onerror = () => void client.invalidateQueries({ queryKey: LATEST_RUN_KEY });
    return () => source.close();
  }, [activeId, client]);

  return query;
}
