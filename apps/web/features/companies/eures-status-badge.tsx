import { EURES_STATUS_LABELS, type EuresStatus } from "@/lib/api/companies";

const TONES: Record<EuresStatus, string> = {
  NOT_CHECKED: "border-border text-muted",
  OPENED: "border-accent/40 text-accent",
  CHECKED_NO_JOBS: "border-border text-foreground",
  JOB_FOUND: "border-success/40 text-success",
  ERROR: "border-danger/40 text-danger",
};

export function EuresStatusBadge({ status }: { status: EuresStatus }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded border px-1.5 py-0.5 text-xs font-medium ${TONES[status]}`}
    >
      {EURES_STATUS_LABELS[status]}
    </span>
  );
}
