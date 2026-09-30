import { z } from "zod";

import { apiFetch } from "./client";

export const healthSchema = z.object({
  status: z.string(),
  detail: z.string().nullable().optional(),
});
export type Health = z.infer<typeof healthSchema>;

export const getHealth = () => apiFetch("/health", healthSchema);
