"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { buttonClass, primaryButtonClass } from "@/components/ui/styles";
import { MatchPanel } from "@/features/matches/match-panel";

import { JobStatusActions } from "./job-status-actions";
import { ApiError } from "@/lib/api/client";
import {
  deleteJob,
  getJob,
  JOB_STATUS_LABELS,
  reviewSource,
  SOURCE_TYPE_LABELS,
  type Job,
} from "@/lib/api/jobs";
import { formatDate, formatDateTime } from "@/lib/format";

const isWebUrl = (url: string) => url.startsWith("https://") || url.startsWith("http://");

export function JobDetail({ jobId }: { jobId: string }) {
  const client = useQueryClient();
  const router = useRouter();
  const {
    data: job,
    isPending,
    isError,
    error,
  } = useQuery({
    queryKey: ["jobs", "detail", jobId],
    queryFn: () => getJob(jobId),
  });

  const refresh = (updated?: Job) => {
    if (updated) client.setQueryData(["jobs", "detail", jobId], updated);
    void client.invalidateQueries({ queryKey: ["jobs"] });
    void client.invalidateQueries({ queryKey: ["companies"] });
    void client.invalidateQueries({ queryKey: ["eures"] });
  };
  const review = useMutation({
    mutationFn: ({ sourceId, action }: { sourceId: string; action: "accept" | "reject" }) =>
      reviewSource(jobId, sourceId, action),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => deleteJob(jobId),
    onSuccess: () => {
      refresh();
      router.push("/jobs");
    },
  });

  if (isPending) return <p className="text-sm text-muted">Loading job…</p>;
  if (isError) {
    const missing = error instanceof ApiError && error.status === 404;
    return (
      <div role="alert" className="space-y-2 text-sm">
        <p className="text-danger">{missing ? "This job does not exist." : error.message}</p>
        <Link href="/jobs" className="text-accent hover:underline">
          Back to jobs
        </Link>
      </div>
    );
  }

  const pending = job.sources.filter((s) => s.status === "PENDING");
  const facts: [string, string | null][] = [
    ["Company", job.company?.company_name ?? job.employer_name],
    ["Location", job.location],
    ["Employment", job.employment_type],
    ["Workplace", job.workplace_type],
    ["Published", job.published_at ? formatDate(job.published_at) : null],
    ["Apply by", job.expires_at ? formatDate(job.expires_at) : null],
    ["Source", SOURCE_TYPE_LABELS[job.source_type]],
    ["Imported", formatDateTime(job.created_at)],
  ];

  return (
    <article className="max-w-4xl space-y-5">
      <header className="space-y-1">
        <Link href="/jobs" className="text-xs text-accent hover:underline">
          ← Jobs
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">
          {job.title}
          {job.status !== "NEW" && (
            <span className="ml-2 align-middle rounded border border-border px-1.5 py-0.5 text-xs font-normal text-muted">
              {JOB_STATUS_LABELS[job.status]}
            </span>
          )}
        </h1>
        <div className="flex flex-wrap gap-2 pt-1">
          {job.apply_url && isWebUrl(job.apply_url) && (
            <a
              href={job.apply_url}
              target="_blank"
              rel="noopener noreferrer"
              className={primaryButtonClass}
            >
              Open original job ↗
            </a>
          )}
          {job.company && (
            <Link href={`/jobs?company=${job.company.id}`} className={buttonClass}>
              All jobs at {job.company.company_name}
            </Link>
          )}
          <JobStatusActions jobId={job.id} title={job.title} status={job.status} />
          <button
            type="button"
            className={buttonClass}
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm(`Delete "${job.title}"? This cannot be undone.`)) remove.mutate();
            }}
          >
            Delete job
          </button>
        </div>
      </header>

      {pending.map((snapshot) => (
        <section
          key={snapshot.id}
          aria-label="Source update to review"
          className="space-y-2 rounded border border-warning/40 p-3 text-sm"
        >
          <p className="font-medium text-warning">
            The original posting changed on {formatDateTime(snapshot.fetched_at)}.
          </p>
          <p className="text-muted">
            New title: <span className="text-foreground">{String(snapshot.normalized.title)}</span>
          </p>
          <details>
            <summary className="cursor-pointer text-accent">Show updated description</summary>
            <p className="mt-2 whitespace-pre-line">{String(snapshot.normalized.description)}</p>
          </details>
          <div className="flex gap-2">
            <button
              type="button"
              className={primaryButtonClass}
              disabled={review.isPending}
              onClick={() => review.mutate({ sourceId: snapshot.id, action: "accept" })}
            >
              Accept update
            </button>
            <button
              type="button"
              className={buttonClass}
              disabled={review.isPending}
              onClick={() => review.mutate({ sourceId: snapshot.id, action: "reject" })}
            >
              Keep current version
            </button>
          </div>
          {review.isError && (
            <p role="alert" className="text-danger">
              {review.error.message}
            </p>
          )}
        </section>
      ))}

      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-muted">{label}</dt>
            <dd>{value ?? "—"}</dd>
          </div>
        ))}
      </dl>

      <MatchPanel jobId={job.id} />

      <section aria-labelledby="description-title" className="space-y-2">
        <h2 id="description-title" className="text-sm font-semibold">
          Job description
        </h2>
        <div className="whitespace-pre-line rounded border border-border p-4 text-sm leading-relaxed">
          {job.description}
        </div>
      </section>

      <section aria-labelledby="sources-title" className="space-y-2">
        <h2 id="sources-title" className="text-sm font-semibold">
          Sources
        </h2>
        <ul className="space-y-1 text-sm">
          {job.sources.map((source) => (
            <li key={source.id} className="flex flex-wrap gap-2">
              <span className="text-muted">{SOURCE_TYPE_LABELS[source.source_type]}</span>
              {isWebUrl(source.source_url) ? (
                <a
                  href={source.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="break-all text-accent hover:underline"
                >
                  {source.source_url}
                </a>
              ) : (
                <span>Pasted manually</span>
              )}
              <span className="text-muted">
                · {source.status.toLowerCase()} · fetched {formatDateTime(source.fetched_at)}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}
