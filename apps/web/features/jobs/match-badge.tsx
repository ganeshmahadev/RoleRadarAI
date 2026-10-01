import { CATEGORY_LABELS } from "@/lib/api/matches";
import type { JobListItem } from "@/lib/api/jobs";

const TONE: Record<string, string> = {
  STRONG: "border-success/40 text-success",
  GOOD: "border-success/40 text-success",
  STRETCH: "border-warning/40 text-warning",
  LOW: "border-border text-muted",
  BLOCKED: "border-danger/40 text-danger",
};

/** Compact Match Score for tables: "84 Good Match" (never a hiring probability). */
export function MatchBadge({
  item,
}: {
  item: Pick<JobListItem, "match" | "match_outdated" | "scoring">;
}) {
  const { match } = item;
  if (!match) {
    return <span className="text-xs text-muted">{item.scoring ? "Scoring…" : "Not scored"}</span>;
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 whitespace-nowrap">
      <span className="font-semibold tabular-nums">{Math.round(match.overall_score)}</span>
      <span
        className={`rounded border px-1 py-px text-xs font-medium ${TONE[match.category] ?? "border-border text-muted"}`}
      >
        {CATEGORY_LABELS[match.category] ?? match.category}
      </span>
      {item.match_outdated && (
        <span
          className="text-xs text-warning"
          title="Your resume, profile or the job changed since scoring"
        >
          outdated
        </span>
      )}
      {item.scoring && <span className="text-xs text-muted">· rescoring…</span>}
    </span>
  );
}
