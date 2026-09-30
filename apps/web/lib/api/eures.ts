import { z } from "zod";

import { ApiError, apiFetch } from "./client";
import { companySchema, euresStatusSchema, type Company } from "./companies";

export const queueStatsSchema = z.object({
  total: z.number().int(),
  checked: z.number().int(),
  remaining: z.number().int(),
  by_status: z.record(euresStatusSchema, z.number().int()),
});
export type QueueStats = z.infer<typeof queueStatsSchema>;

export const getQueueStats = () => apiFetch("/eures/stats", queueStatsSchema);

/** Next NOT_CHECKED/OPENED company in SIRI order; null when the queue is done. */
export async function getNextUnchecked(afterPosition?: number | null): Promise<Company | null> {
  const qs = afterPosition != null ? `?after_position=${afterPosition}` : "";
  try {
    return await apiFetch(`/eures/next-unchecked${qs}`, companySchema);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export type EuresAction = "eures-opened" | "mark-no-jobs" | "mark-eures-error" | "reset-eures";

export const runEuresAction = (companyId: string, action: EuresAction) =>
  apiFetch(`/companies/${companyId}/${action}`, companySchema, { method: "POST" });

export const updateEuresNotes = (companyId: string, notes: string) =>
  apiFetch(`/companies/${companyId}`, companySchema, {
    method: "PATCH",
    body: JSON.stringify({ eures_notes: notes }),
  });
