import { z } from "zod";

import { API_BASE_URL, apiFetch } from "./client";

export const runStatusSchema = z.enum(["QUEUED", "RUNNING", "DONE", "CANCELLED", "FAILED"]);
export type RunStatus = z.infer<typeof runStatusSchema>;
export const runScopeSchema = z.enum(["unscored", "unscored_or_outdated", "jobs"]);
export type RunScope = z.infer<typeof runScopeSchema>;

const plannedJobSchema = z.object({
  job_id: z.string(),
  title: z.string(),
  matched_role: z.string().nullable(),
});

export const runPlanSchema = z.object({
  scope: runScopeSchema,
  relevance_filter: z.boolean(),
  target_roles: z.array(z.string()),
  to_score: z.array(plannedJobSchema),
  not_relevant: z.array(plannedJobSchema),
  seconds_per_job: z.number().nullable(),
});
export type RunPlan = z.infer<typeof runPlanSchema>;

const runItemSchema = z.object({
  job_id: z.string(),
  job_title: z.string(),
  status: z.enum(["PENDING", "RUNNING", "DONE", "CACHED", "SKIPPED", "FAILED"]),
  reason: z.string().nullable(),
  error_code: z.string().nullable(),
  matched_role: z.string().nullable(),
  match_id: z.string().nullable(),
  completed_at: z.string().nullable(),
});
export type RunItem = z.infer<typeof runItemSchema>;

export const runSchema = z.object({
  id: z.string(),
  status: runStatusSchema,
  scope: runScopeSchema,
  relevance_filter: z.boolean(),
  target_roles: z.array(z.string()),
  counts: z.record(z.string(), z.number().int()),
  finished: z.number().int(),
  total: z.number().int(),
  current_job_id: z.string().nullable(),
  current_job_title: z.string().nullable(),
  seconds_per_job: z.number().nullable(),
  seconds_remaining: z.number().nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  items: z.array(runItemSchema),
});
export type Run = z.infer<typeof runSchema>;

export const isRunActive = (status: RunStatus) => status === "QUEUED" || status === "RUNNING";

export interface RunRequest {
  scope: RunScope;
  apply_relevance_filter: boolean;
  job_ids?: string[];
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const previewRun = (request: RunRequest) =>
  apiFetch("/match-runs/preview", runPlanSchema, post(request));
export const startRun = (request: RunRequest) => apiFetch("/match-runs", runSchema, post(request));
export const getRun = (id: string) => apiFetch(`/match-runs/${id}`, runSchema);
export const latestRun = async () =>
  (await apiFetch("/match-runs?limit=1", z.array(runSchema)))[0] ?? null;
export const cancelRun = (id: string) =>
  apiFetch(`/match-runs/${id}/cancel`, runSchema, { method: "POST" });
export const runEventsUrl = (id: string) => `${API_BASE_URL}/api/v1/match-runs/${id}/events`;

/** "about 25 min" style estimates; never more precise than the data allows. */
export function formatDuration(seconds: number | null): string | null {
  if (seconds === null || !Number.isFinite(seconds)) return null;
  if (seconds < 90) return "about a minute";
  const minutes = Math.round(seconds / 60);
  if (minutes < 90) return `about ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `about ${hours} h ${minutes % 60} min`;
}
