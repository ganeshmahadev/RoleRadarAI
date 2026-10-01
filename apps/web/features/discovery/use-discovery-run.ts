"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import {
  discoveryEventsUrl,
  discoveryRunSchema,
  latestDiscoveryRun,
  type DiscoveryRun,
} from "@/lib/api/discovery";
import { isRunActive } from "@/lib/api/match-runs";

export const LATEST_DISCOVERY_KEY = ["discovery-runs", "latest"] as const;
const POLL_MS = 5000;

/** Latest discovery run, live through SSE with polling as the fallback (same as batch runs). */
export function useLatestDiscovery() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: LATEST_DISCOVERY_KEY,
    queryFn: latestDiscoveryRun,
    refetchInterval: (q) => {
      const run = q.state.data;
      const streaming = typeof window !== "undefined" && "EventSource" in window;
      return run && isRunActive(run.status) && !streaming ? POLL_MS : false;
    },
  });
  const run = query.data;

  // New jobs and scores show up in the job lists as soon as they are stored.
  const progress = run
    ? `${run.new_jobs.length}:${run.scoring?.finished ?? 0}:${run.status}`
    : null;
  const last = useRef(progress);
  useEffect(() => {
    if (progress !== last.current) void client.invalidateQueries({ queryKey: ["jobs"] });
    last.current = progress;
  }, [progress, client]);

  const activeId = run && isRunActive(run.status) ? run.id : null;
  useEffect(() => {
    if (!activeId || typeof window === "undefined" || !("EventSource" in window)) return;
    const source = new EventSource(discoveryEventsUrl(activeId));
    source.addEventListener("progress", (event) => {
      const parsed = discoveryRunSchema.safeParse(JSON.parse((event as MessageEvent<string>).data));
      if (parsed.success)
        client.setQueryData<DiscoveryRun | null>(LATEST_DISCOVERY_KEY, parsed.data);
    });
    source.addEventListener("end", () => source.close());
    source.onerror = () => void client.invalidateQueries({ queryKey: LATEST_DISCOVERY_KEY });
    return () => source.close();
  }, [activeId, client]);

  return query;
}
