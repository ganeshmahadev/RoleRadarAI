"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { buttonClass } from "@/components/ui/styles";
import { updateJobStatus, type JobStatus } from "@/lib/api/jobs";

const small = `${buttonClass} h-7 px-2 text-xs`;

/** Save / Ignore toggles (PRD §5.1). Ignored jobs drop out of lists by default. */
export function JobStatusActions({
  jobId,
  title,
  status,
}: {
  jobId: string;
  title: string;
  status: JobStatus;
}) {
  const client = useQueryClient();
  const update = useMutation({
    mutationFn: (next: JobStatus) => updateJobStatus(jobId, next),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const set = (next: JobStatus) => update.mutate(next);

  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      {status === "IGNORED" ? (
        <button
          type="button"
          className={small}
          disabled={update.isPending}
          onClick={() => set("NEW")}
          aria-label={`Restore ${title}`}
        >
          Restore
        </button>
      ) : (
        <>
          <button
            type="button"
            className={small}
            disabled={update.isPending}
            aria-pressed={status === "SAVED"}
            onClick={() => set(status === "SAVED" ? "NEW" : "SAVED")}
            aria-label={status === "SAVED" ? `Unsave ${title}` : `Save ${title}`}
          >
            {status === "SAVED" ? "★ Saved" : "☆ Save"}
          </button>
          <button
            type="button"
            className={small}
            disabled={update.isPending}
            onClick={() => set("IGNORED")}
            aria-label={`Ignore ${title}`}
          >
            Ignore
          </button>
        </>
      )}
      {update.isError && (
        <span role="alert" className="text-xs text-danger">
          {update.error.message}
        </span>
      )}
    </span>
  );
}
