"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { buttonClass, inputClass, primaryButtonClass } from "@/components/ui/styles";
import { errorCode } from "@/lib/api/client";
import { formatDuration, previewRun, startRun, type RunScope } from "@/lib/api/match-runs";

import { LATEST_RUN_KEY } from "./use-run-progress";

export function BatchDialog({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  const client = useQueryClient();
  const [scope, setScope] = useState<RunScope>("unscored_or_outdated");
  const [filter, setFilter] = useState(true);
  const request = { scope, apply_relevance_filter: filter };

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const plan = useQuery({
    queryKey: ["match-runs", "preview", request],
    queryFn: () => previewRun(request),
  });
  const start = useMutation({
    mutationFn: () => startRun(request),
    onSuccess: (run) => {
      client.setQueryData(LATEST_RUN_KEY, run);
      onClose();
    },
  });

  const count = plan.data?.to_score.length ?? 0;
  const estimate = formatDuration(
    plan.data?.seconds_per_job != null ? plan.data.seconds_per_job * count : null,
  );

  return (
    <dialog
      ref={ref}
      aria-labelledby={`${id}-title`}
      onClose={onClose}
      className="m-auto w-full max-w-xl rounded border border-border bg-background p-0 text-foreground backdrop:bg-black/40"
    >
      <form
        className="space-y-4 p-4"
        onSubmit={(event) => {
          event.preventDefault();
          start.mutate();
        }}
      >
        <h2 id={`${id}-title`} className="text-base font-semibold">
          Score jobs in the background
        </h2>
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-scope`} className="text-xs font-medium text-muted">
              Jobs
            </label>
            <select
              id={`${id}-scope`}
              value={scope}
              onChange={(e) => setScope(e.target.value as RunScope)}
              className={inputClass}
            >
              <option value="unscored_or_outdated">Not scored yet or outdated</option>
              <option value="unscored">Not scored yet</option>
            </select>
          </div>
          <label className="flex h-8 items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={filter}
              onChange={(e) => setFilter(e.target.checked)}
              className="size-4 accent-accent"
            />
            Only titles matching my target roles
          </label>
        </div>

        {plan.isPending && <div className="h-20 animate-pulse rounded bg-surface" />}
        {plan.isError && (
          <p role="alert" className="text-sm text-danger">
            {errorCode(plan.error) === "NO_PRIMARY_RESUME" ? (
              <>
                Upload your resume first in{" "}
                <Link href="/settings/profile" className="underline">
                  Settings → Profile &amp; resume
                </Link>
                .
              </>
            ) : (
              plan.error.message
            )}
          </p>
        )}
        {plan.data && (
          <div className="space-y-2 text-sm">
            {filter && !plan.data.relevance_filter && (
              <p className="text-warning">
                Your profile has no target roles, so every title is included. Add them in{" "}
                <Link href="/settings/profile" className="underline">
                  your profile
                </Link>{" "}
                to skip irrelevant jobs.
              </p>
            )}
            {plan.data.relevance_filter && (
              <p className="text-muted">Target roles: {plan.data.target_roles.join(", ")}</p>
            )}
            <p>
              <span className="font-semibold">{count}</span> {count === 1 ? "job" : "jobs"} will be
              scored
              {plan.data.not_relevant.length > 0 &&
                `, ${plan.data.not_relevant.length} skipped as not relevant`}
              .{estimate && ` This takes ${estimate} at the current speed.`}
            </p>
            {count > 0 && (
              <details>
                <summary className="cursor-pointer text-accent">Jobs to score</summary>
                <ul className="mt-1 max-h-40 list-disc overflow-auto pl-5">
                  {plan.data.to_score.map((job) => (
                    <li key={job.job_id}>{job.title}</li>
                  ))}
                </ul>
              </details>
            )}
            {plan.data.not_relevant.length > 0 && (
              <details>
                <summary className="cursor-pointer text-accent">Skipped as not relevant</summary>
                <ul className="mt-1 max-h-40 list-disc overflow-auto pl-5 text-muted">
                  {plan.data.not_relevant.map((job) => (
                    <li key={job.job_id}>{job.title}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
        {start.isError && (
          <p role="alert" className="text-sm text-danger">
            {start.error.message}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" className={buttonClass} onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className={primaryButtonClass} disabled={!count || start.isPending}>
            {start.isPending ? "Starting…" : `Score ${count} ${count === 1 ? "job" : "jobs"}`}
          </button>
        </div>
      </form>
    </dialog>
  );
}
