"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { ReactNode } from "react";

import { MatchBadge } from "@/features/jobs/match-badge";
import { MATCHES_QUERY } from "@/features/matches/matches-view";
import { getQueueStats } from "@/lib/api/eures";
import { countJobs, DEFAULT_JOB_QUERY, listJobs, type JobListItem } from "@/lib/api/jobs";
import { formatDate } from "@/lib/format";

const COUNTS: [string, Record<string, string>][] = [
  ["active", {}],
  ["scored", { scored: "true" }],
  ["strong", { category: "STRONG" }],
  ["saved", { status: "SAVED" }],
  ["unscored", { scored: "false" }],
  ["pending", { update_pending: "true" }],
];

/** PRD §33, limited to data that exists today (applications arrive in P8). */
export function DashboardView() {
  const stats = useQuery({ queryKey: ["eures", "stats"], queryFn: getQueueStats });
  const counts = useQueries({
    queries: COUNTS.map(([key, params]) => ({
      queryKey: ["jobs", "count", key],
      queryFn: () => countJobs(params),
    })),
  });
  const [active, scored, strong, saved, unscored, pending] = counts;

  const top = useQuery({
    queryKey: ["jobs", "list", { ...MATCHES_QUERY, pageSize: 5 }],
    queryFn: () => listJobs({ ...MATCHES_QUERY, pageSize: 5 }),
  });
  const recent = useQuery({
    queryKey: ["jobs", "list", { ...DEFAULT_JOB_QUERY, pageSize: 5 }],
    queryFn: () => listJobs({ ...DEFAULT_JOB_QUERY, pageSize: 5 }),
  });

  const tiles: [string, number | undefined, string][] = [
    ["SIRI companies", stats.data?.total, "/companies"],
    ["Companies checked", stats.data?.checked, "/eures"],
    ["Active jobs", active.data, "/jobs"],
    ["Scored jobs", scored.data, "/matches"],
    ["Strong matches", strong.data, "/matches?cat=STRONG"],
    ["Saved jobs", saved.data, "/jobs?status=SAVED"],
  ];

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded border border-border bg-border sm:grid-cols-3 lg:grid-cols-6">
        {tiles.map(([label, value, href]) => (
          <div key={label} className="bg-background p-3">
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="text-xl font-semibold tabular-nums">
              <Link href={href} className="hover:underline">
                {value ?? "–"}
              </Link>
            </dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Top matches" more={{ href: "/matches", label: "All matches" }}>
          <JobList
            items={top.data?.items}
            error={top.error}
            empty="No scored jobs yet. Open a job and score it against your resume."
            right={(item) => <MatchBadge item={item} />}
          />
        </Section>
        <Section title="Recently discovered" more={{ href: "/jobs", label: "All jobs" }}>
          <JobList
            items={recent.data?.items}
            error={recent.error}
            empty="No jobs yet. Import one from the EURES queue or the Jobs page."
            right={(item) => (
              <span className="text-xs text-muted">{formatDate(item.created_at)}</span>
            )}
          />
        </Section>
      </div>

      <Section title="Needs review">
        <ul className="space-y-1 text-sm">
          <li>
            <Link href="/jobs?sort=newest" className="text-accent hover:underline">
              {unscored.data ?? "–"} jobs not scored yet
            </Link>
          </li>
          <li>
            <Link href="/jobs" className="text-accent hover:underline">
              {pending.data ?? "–"} jobs whose original posting changed
            </Link>
          </li>
          <li>
            <Link href="/eures" className="text-accent hover:underline">
              {stats.data?.remaining ?? "–"} companies still to check on EURES
            </Link>
          </li>
        </ul>
      </Section>
    </div>
  );
}

function Section({
  title,
  more,
  children,
}: {
  title: string;
  more?: { href: string; label: string };
  children: ReactNode;
}) {
  return (
    <section aria-label={title} className="space-y-2">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold">{title}</h2>
        {more && (
          <Link href={more.href} className="text-xs text-accent hover:underline">
            {more.label} →
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

function JobList({
  items,
  error,
  empty,
  right,
}: {
  items: JobListItem[] | undefined;
  error: Error | null;
  empty: string;
  right: (item: JobListItem) => ReactNode;
}) {
  if (error)
    return (
      <p role="alert" className="text-sm text-danger">
        {error.message}
      </p>
    );
  if (!items) return <div className="h-32 animate-pulse rounded border border-border bg-surface" />;
  if (items.length === 0) return <p className="text-sm text-muted">{empty}</p>;
  return (
    <ul className="divide-y divide-border rounded border border-border">
      {items.map((item) => (
        <li key={item.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
          <span className="min-w-0">
            <Link href={`/jobs/${item.id}`} className="font-medium hover:underline">
              {item.title}
            </Link>
            <span className="block truncate text-xs text-muted">
              {item.company?.company_name ?? item.employer_name ?? "Unknown company"}
              {item.location && ` · ${item.location}`}
            </span>
          </span>
          {right(item)}
        </li>
      ))}
    </ul>
  );
}
