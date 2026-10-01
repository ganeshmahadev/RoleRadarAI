"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";

import { buttonClass, primaryButtonClass } from "@/components/ui/styles";
import { errorCode } from "@/lib/api/client";
import {
  CATEGORY_LABELS,
  DIMENSION_LABELS,
  isActive,
  latestMatchForJob,
  scoreJob,
  type Match,
  type RequirementCheck,
} from "@/lib/api/matches";
import { formatDateTime } from "@/lib/format";

const POLL_MS = 3000;

/** Match Score for one job against the primary resume (PRD §20, §32, §49). */
export function MatchPanel({ jobId }: { jobId: string }) {
  const client = useQueryClient();
  const key = ["matches", "job", jobId];
  const {
    data: match,
    isPending,
    isError,
    error,
  } = useQuery({
    queryKey: key,
    queryFn: () => latestMatchForJob(jobId),
    refetchInterval: (query) =>
      query.state.data && isActive(query.state.data.status) ? POLL_MS : false,
  });
  const score = useMutation({
    mutationFn: () => scoreJob(jobId),
    onSuccess: (response) => client.setQueryData(key, response.match),
  });

  const scoreButton = (label: string) => (
    <button
      type="button"
      className={label.startsWith("Score") ? primaryButtonClass : buttonClass}
      disabled={score.isPending || (match ? isActive(match.status) : false)}
      onClick={() => score.mutate()}
    >
      {score.isPending ? "Requesting…" : label}
    </button>
  );

  return (
    <section aria-labelledby="match-title" className="space-y-3 rounded border border-border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="match-title" className="text-sm font-semibold">
          Match Score
        </h2>
        {match?.status === "DONE" && scoreButton("Check again")}
      </div>

      {score.isError && <ScoreError error={score.error} />}
      {isPending && <div className="h-20 animate-pulse rounded bg-surface" />}
      {isError && (
        <p role="alert" className="text-sm text-danger">
          {error.message}
        </p>
      )}
      {!isPending && !isError && !match && (
        <div className="space-y-2 text-sm">
          <p className="text-muted">
            Not scored yet. OpenJev compares this job with your primary resume and profile; it runs
            in the background and can take a few minutes.
          </p>
          {scoreButton("Score against my resume")}
        </div>
      )}
      {match && isActive(match.status) && <Running match={match} />}
      {match?.status === "FAILED" && (
        <div role="alert" className="space-y-2 text-sm">
          <p className="text-danger">Scoring failed: {match.error_message ?? match.error_code}</p>
          {scoreButton("Score again")}
        </div>
      )}
      {match?.status === "DONE" && <MatchResult match={match} />}
    </section>
  );
}

function ScoreError({ error }: { error: Error }) {
  const code = errorCode(error);
  return (
    <p role="alert" className="text-sm text-danger">
      {code === "NO_PRIMARY_RESUME" ? (
        <>
          Upload your resume first in{" "}
          <Link href="/settings/profile" className="underline">
            Settings → Profile &amp; resume
          </Link>
          .
        </>
      ) : code === "DECISION_PROVIDER_UNAVAILABLE" ? (
        <>
          OpenJev is not running. Start it with{" "}
          <code className="font-mono">~/models/openjev/start-openjev.sh</code> and try again.
        </>
      ) : (
        error.message
      )}
    </p>
  );
}

function useElapsed(since: string) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.round((now - new Date(since).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function Running({ match }: { match: Match }) {
  const elapsed = useElapsed(match.started_at ?? match.created_at);
  return (
    <p role="status" className="text-sm">
      {match.status === "QUEUED" ? "Queued for scoring" : "Scoring with OpenJev"} · {elapsed}
      <span className="block text-xs text-muted">
        This page updates by itself; you can keep working elsewhere.
        {match.error_message && ` Last attempt: ${match.error_message}`}
      </span>
    </p>
  );
}

const STATUS_ICON: Record<
  RequirementCheck["status"],
  { icon: string; tone: string; text: string }
> = {
  MET: { icon: "✓", tone: "text-success", text: "Met" },
  PARTIAL: { icon: "△", tone: "text-warning", text: "Partly met" },
  NOT_MET: { icon: "✗", tone: "text-danger", text: "Not met" },
  UNKNOWN: { icon: "–", tone: "text-muted", text: "Not required by this job" },
};

function MatchResult({ match }: { match: Match }) {
  const score = Math.round(match.overall_score ?? 0);
  const blockers = match.requirements.filter((r) => r.classification === "blocker");
  const stated = match.requirements.filter((r) => r.status !== "UNKNOWN");
  const notStated = match.requirements.filter((r) => r.status === "UNKNOWN");
  const category = match.category ?? "";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-3">
        <p className="text-3xl font-semibold tabular-nums">
          {score}
          <span className="text-base font-normal text-muted"> / 100</span>
        </p>
        <span
          className={`rounded border px-1.5 py-0.5 text-xs font-medium ${
            category === "BLOCKED"
              ? "border-danger/40 text-danger"
              : category === "STRONG" || category === "GOOD"
                ? "border-success/40 text-success"
                : "border-border text-muted"
          }`}
        >
          {CATEGORY_LABELS[category] ?? category}
          {blockers.length > 0 &&
            `: ${blockers.map((b) => b.label.toLowerCase()).join(", ")} not met`}
        </span>
      </div>
      {blockers.length > 0 && (
        <p className="text-xs text-muted">
          The score still shows how well you fit; a blocker means the job states a mandatory
          requirement you do not appear to meet. Check the job text before deciding.
        </p>
      )}

      <dl className="space-y-1.5">
        {DIMENSION_LABELS.map(([key, label]) => {
          const value = match.dimensions[key];
          return (
            <div key={key} className="grid grid-cols-[12rem_1fr_3rem] items-center gap-3 text-sm">
              <dt>{label}</dt>
              <dd className="h-2 rounded bg-surface" aria-hidden="true">
                {value !== null && (
                  <div className="h-2 rounded bg-accent" style={{ width: `${value}%` }} />
                )}
              </dd>
              <dd className="text-right tabular-nums">
                {value === null ? (
                  <span className="text-xs text-muted" title="The job states no hard requirement">
                    n/a
                  </span>
                ) : (
                  Math.round(value)
                )}
              </dd>
            </div>
          );
        })}
      </dl>

      <div className="space-y-1">
        <h3 className="text-xs font-medium text-muted">Hard requirements stated by the job</h3>
        {stated.length === 0 ? (
          <p className="text-sm text-muted">None detected.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {stated.map((r) => (
              <li key={r.key} className="flex gap-2">
                <span aria-hidden="true" className={STATUS_ICON[r.status].tone}>
                  {STATUS_ICON[r.status].icon}
                </span>
                <span>
                  {r.label}
                  <span className="sr-only"> — </span>
                  <span className={`ml-2 text-xs ${STATUS_ICON[r.status].tone}`}>
                    {STATUS_ICON[r.status].text}
                    {r.met_probability !== null && ` (${Math.round(r.met_probability * 100)}%)`}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
        {notStated.length > 0 && (
          <p className="text-xs text-muted">
            Not required by this job: {notStated.map((r) => r.label.toLowerCase()).join(", ")}.
          </p>
        )}
      </div>

      <p className="text-xs text-muted">
        Scored {formatDateTime(match.completed_at)} with {match.model_name} · {match.rubric_version}
        {match.duration_ms !== null && ` · took ${Math.round(match.duration_ms / 1000)}s`}. This is
        a fit score under your rubric, not a chance of being hired.
      </p>
    </div>
  );
}
