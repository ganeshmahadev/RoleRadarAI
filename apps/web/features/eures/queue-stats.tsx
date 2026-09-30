"use client";

import { useQuery } from "@tanstack/react-query";

import { getQueueStats } from "@/lib/api/eures";

export function QueueStats() {
  const { data, isError } = useQuery({ queryKey: ["eures", "stats"], queryFn: getQueueStats });
  if (isError) return <p className="text-sm text-danger">Queue statistics unavailable.</p>;
  const items = [
    ["companies", data?.total],
    ["checked", data?.checked],
    ["remaining", data?.remaining],
  ] as const;
  return (
    <dl className="flex flex-wrap gap-6 text-sm" aria-live="polite">
      {items.map(([label, value]) => (
        <div key={label} className="flex items-baseline gap-1.5">
          <dt className="sr-only">{label}</dt>
          <dd className="text-lg font-semibold tabular-nums">{value ?? "–"}</dd>
          <span aria-hidden="true" className="text-muted">
            {label}
          </span>
        </div>
      ))}
    </dl>
  );
}
