"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";

import { buttonClass } from "@/components/ui/styles";
import {
  cancelDiscovery,
  SITE_LABELS,
  type DiscoveryRun,
  type SourceEntry,
} from "@/lib/api/discovery";
import { formatDuration, isRunActive, type RunItem } from "@/lib/api/match-runs";
import { formatDateTime } from "@/lib/format";

import { LATEST_DISCOVERY_KEY } from "./use-discovery-run";

const PHASES = [
  ["SCRAPING", "Job boards"],
  ["EURES", "EURES"],
  ["SCORING", "Scoring"],
  ["FINISHED", "Done"],
] as const;

const STATUS_LABELS: Record<string, string> = {
  ok: "OK",
  blocked: "Blocked",
  skipped: "Skipped",
  error: "Error",
  disabled: "Off",
};

const RESULT_LABELS: Record<RunItem["status"], string> = {
  PENDING: "Waiting",
  RUNNING: "Scoring now",
  DONE: "Scored",
  CACHED: "Scored",
  SKIPPED: "Not scored",
  FAILED: "Failed",
};

const TITLES: Record<string, string> = {
  QUEUED: "Search queued",
  RUNNING: "Searching",
  DONE: "Last search finished",
  CANCELLED: "Last search cancelled",
  FAILED: "Last search stopped",
};

export function DiscoveryRunPanel({ run }: { run: DiscoveryRun }) {
  const client = useQueryClient();
  const active = isRunActive(run.status);
  const cancel = useMutation({
    mutationFn: () => cancelDiscovery(run.id),
    onSuccess: (updated) => client.setQueryData(LATEST_DISCOVERY_KEY, updated),
  });
  const scoring = run.scoring;
  const remaining =
    scoring && isRunActive(scoring.status) ? formatDuration(scoring.seconds_remaining) : null;
  const created = run.sources.reduce((sum, s) => sum + s.created, 0);
  const items = new Map(scoring?.items.map((i) => [i.job_id, i]));
  const scored = scoring?.items.filter((i) => i.status === "DONE" || i.status === "CACHED") ?? [];

  return (
    <section
      aria-label="Latest search"
      className="space-y-3 rounded border border-border p-4 text-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">{TITLES[run.status]}</h2>
          <p className="text-xs text-muted">
            {run.trigger === "scheduled" ? "Daily run" : "Started by you"} ·{" "}
            {formatDateTime(run.started_at ?? run.created_at)}
            {run.completed_at && ` → ${formatDateTime(run.completed_at)}`}
          </p>
        </div>
        {active && (
          <button
            type="button"
            className={`${buttonClass} h-7 px-2 text-xs`}
            disabled={cancel.isPending || run.status === "CANCELLED"}
            onClick={() => cancel.mutate()}
          >
            {cancel.isSuccess ? "Stopping…" : "Cancel search"}
          </button>
        )}
      </div>

      <ol aria-label="Phases" className="flex flex-wrap gap-2 text-xs">
        {PHASES.map(([phase, label]) => {
          const index = PHASES.findIndex(([p]) => p === run.phase);
          const mine = PHASES.findIndex(([p]) => p === phase);
          const state =
            mine < index || run.phase === "FINISHED" ? "done" : mine === index ? "current" : "todo";
          return (
            <li
              key={phase}
              aria-current={state === "current" ? "step" : undefined}
              className={`rounded border px-2 py-0.5 ${
                state === "current"
                  ? "border-accent font-medium text-accent"
                  : state === "done"
                    ? "border-border"
                    : "border-border text-muted"
              }`}
            >
              {state === "done" ? "✓ " : ""}
              {label}
            </li>
          );
        })}
      </ol>

      <p role="status">
        {created} new job{created === 1 ? "" : "s"}
        {scoring && ` · ${scoring.finished} of ${scoring.total} relevant jobs scored`}
        {remaining && ` · ${remaining} left`}
      </p>
      {run.error_message && <p className="text-danger">{run.error_message}</p>}

      {run.sources.length > 0 && <SourcesTable sources={run.sources} />}

      {run.new_jobs.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-xs font-medium text-muted">New jobs</h3>
          <ul className="divide-y divide-border rounded border border-border">
            {run.new_jobs.map((job) => {
              const item = items.get(job.id);
              return (
                <li
                  key={job.id}
                  className="flex flex-wrap items-center justify-between gap-2 px-2 py-1.5"
                >
                  <Link
                    href={`/jobs/${job.id}`}
                    className="text-accent underline-offset-2 hover:underline"
                  >
                    {job.title}
                  </Link>
                  <span className="text-xs text-muted">
                    {SITE_LABELS[job.source] ?? job.source}
                    {item && ` · ${RESULT_LABELS[item.status]}`}
                    {item?.status === "SKIPPED" && item.reason && ` (${item.reason})`}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {scored.length > 0 && (
        <p>
          <Link href="/matches" className="text-accent underline">
            See ranked matches
          </Link>
        </p>
      )}
    </section>
  );
}

function SourcesTable({ sources }: { sources: SourceEntry[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <caption className="sr-only">Results per source</caption>
        <thead className="text-muted">
          <tr>
            <th scope="col" className="py-1 pr-3 font-medium">
              Source
            </th>
            <th scope="col" className="py-1 pr-3 font-medium">
              Search
            </th>
            <th scope="col" className="py-1 pr-3 font-medium">
              Status
            </th>
            <th scope="col" className="py-1 pr-3 text-right font-medium">
              Found
            </th>
            <th scope="col" className="py-1 pr-3 text-right font-medium">
              New
            </th>
            <th scope="col" className="py-1 pr-3 text-right font-medium">
              Already known
            </th>
            <th scope="col" className="py-1 pr-3 text-right font-medium">
              SIRI company
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sources.map((s, i) => (
            <tr key={`${s.source}-${s.term}-${i}`}>
              <th scope="row" className="py-1 pr-3 font-normal">
                {SITE_LABELS[s.source] ?? s.source}
              </th>
              <td className="py-1 pr-3">
                {s.companies_scanned !== undefined
                  ? `${s.companies_scanned} companies`
                  : (s.term ?? "—")}
              </td>
              <td
                className={`py-1 pr-3 ${s.status === "blocked" || s.status === "error" ? "text-danger" : ""}`}
              >
                {STATUS_LABELS[s.status] ?? s.status}
                {s.message && <span className="block text-muted">{s.message}</span>}
              </td>
              <td className="py-1 pr-3 text-right tabular-nums">{s.found}</td>
              <td className="py-1 pr-3 text-right tabular-nums">{s.created}</td>
              <td className="py-1 pr-3 text-right tabular-nums">{s.attached + s.unchanged}</td>
              <td className="py-1 pr-3 text-right tabular-nums">{s.linked_siri}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
