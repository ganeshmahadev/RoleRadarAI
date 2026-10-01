"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { buttonClass } from "@/components/ui/styles";
import { cancelRun, formatDuration, isRunActive, type Run } from "@/lib/api/match-runs";

import { BatchDialog } from "./batch-dialog";
import { LATEST_RUN_KEY, useLatestRun } from "./use-run-progress";

/** Batch scoring (PRD §57): start a run, follow it live, see what happened. */
export function BatchPanel() {
  const { data: run } = useLatestRun();
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const active = run ? isRunActive(run.status) : false;
  const showSummary = run && !active && dismissed !== run.id;

  return (
    <section aria-label="Batch scoring" className="space-y-2">
      {run && active && <RunProgress run={run} />}
      {showSummary && <RunSummary run={run} onDismiss={() => setDismissed(run.id)} />}
      {!active && (
        <button type="button" className={buttonClass} onClick={() => setOpen(true)}>
          Score jobs in bulk…
        </button>
      )}
      {open && <BatchDialog onClose={() => setOpen(false)} />}
    </section>
  );
}

function RunProgress({ run }: { run: Run }) {
  const client = useQueryClient();
  const cancel = useMutation({
    mutationFn: () => cancelRun(run.id),
    onSuccess: (updated) => client.setQueryData(LATEST_RUN_KEY, updated),
  });
  const percent = run.total ? Math.round((run.finished / run.total) * 100) : 0;
  const remaining = formatDuration(run.seconds_remaining);
  const cancelling = run.status === "RUNNING" && cancel.isSuccess;

  return (
    <div className="space-y-2 rounded border border-border p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p role="status">
          {run.status === "QUEUED" ? "Batch queued" : "Scoring in the background"} · {run.finished}{" "}
          of {run.total} done
          {remaining && ` · ${remaining} left`}
        </p>
        <button
          type="button"
          className={`${buttonClass} h-7 px-2 text-xs`}
          disabled={cancel.isPending || cancelling}
          onClick={() => cancel.mutate()}
        >
          {cancelling ? "Stopping after this job…" : "Cancel batch"}
        </button>
      </div>
      <div
        role="progressbar"
        aria-label="Batch progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="h-2 rounded bg-surface"
      >
        <div
          className="h-2 rounded bg-accent transition-[width]"
          style={{ width: `${percent}%` }}
        />
      </div>
      {run.current_job_title && <p className="text-xs text-muted">Now: {run.current_job_title}</p>}
    </div>
  );
}

function RunSummary({ run, onDismiss }: { run: Run; onDismiss: () => void }) {
  const c = run.counts;
  const failed = run.items.filter((i) => i.status === "FAILED");
  const parts = [
    `${c.DONE ?? 0} scored`,
    c.CACHED ? `${c.CACHED} already up to date` : null,
    c.SKIPPED ? `${c.SKIPPED} skipped` : null,
    c.FAILED ? `${c.FAILED} failed` : null,
  ].filter(Boolean);
  const label = { DONE: "Batch finished", CANCELLED: "Batch cancelled", FAILED: "Batch stopped" }[
    run.status as "DONE" | "CANCELLED" | "FAILED"
  ];

  return (
    <div
      role={run.status === "FAILED" ? "alert" : "status"}
      className={`space-y-1 rounded border p-3 text-sm ${run.status === "FAILED" ? "border-danger/40" : "border-border"}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p>
          <span className="font-medium">{label}:</span> {parts.join(", ")}.
        </p>
        <button type="button" className="text-xs text-accent underline" onClick={onDismiss}>
          Dismiss
        </button>
      </div>
      {run.error_message && <p className="text-danger">{run.error_message}</p>}
      {failed.length > 0 && (
        <details>
          <summary className="cursor-pointer text-accent">Failed jobs</summary>
          <ul className="mt-1 list-disc pl-5">
            {failed.map((item) => (
              <li key={item.job_id}>
                {item.job_title}: {item.reason ?? item.error_code}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
