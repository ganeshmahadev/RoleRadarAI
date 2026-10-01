import { z } from "zod";

import { apiFetch } from "./client";

export const matchStatusSchema = z.enum(["QUEUED", "RUNNING", "DONE", "FAILED"]);
export type MatchStatus = z.infer<typeof matchStatusSchema>;

const requirementSchema = z.object({
  key: z.string(),
  label: z.string(),
  status: z.enum(["MET", "PARTIAL", "NOT_MET", "UNKNOWN"]),
  classification: z.enum(["blocker", "warning", "informational", "none"]),
  stated_probability: z.number(),
  met_probability: z.number().nullable(),
});
export type RequirementCheck = z.infer<typeof requirementSchema>;

const dimensionValue = z.number().nullable();
export const dimensionsSchema = z.object({
  must_have: dimensionValue,
  skills: dimensionValue,
  experience: dimensionValue,
  role: dimensionValue,
  seniority: dimensionValue,
  domain: dimensionValue,
  education: dimensionValue,
});
export type Dimensions = z.infer<typeof dimensionsSchema>;

export const matchSchema = z.object({
  id: z.string(),
  job_id: z.string(),
  resume_id: z.string(),
  status: matchStatusSchema,
  overall_score: z.number().nullable(),
  category: z.string().nullable(),
  hard_blocker: z.boolean(),
  dimensions: dimensionsSchema,
  requirements: z.array(requirementSchema),
  matched_requirements: z.array(z.string()),
  uncertain_requirements: z.array(z.string()),
  missing_requirements: z.array(z.string()),
  explanation: z.record(z.string(), z.unknown()),
  model_provider: z.string(),
  model_name: z.string(),
  model_revision: z.string(),
  rubric_version: z.string(),
  input_hash: z.string(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  attempts: z.number().int(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  completed_at: z.string().nullable(),
  duration_ms: z.number().int().nullable(),
  outdated: z.boolean(),
});
export type Match = z.infer<typeof matchSchema>;

export const scoreResponseSchema = z.object({ match: matchSchema, cached: z.boolean() });

/** Labels per PRD §21; a blocker replaces the band (decision 2026-10-02). Never a hiring probability. */
export const CATEGORY_LABELS: Record<string, string> = {
  STRONG: "Strong Match",
  GOOD: "Good Match",
  STRETCH: "Stretch",
  LOW: "Low Match",
  BLOCKED: "Blocked",
};

export const DIMENSION_LABELS: [keyof Dimensions, string][] = [
  ["must_have", "Must-have requirements"],
  ["skills", "Skills"],
  ["experience", "Experience"],
  ["role", "Role alignment"],
  ["seniority", "Seniority"],
  ["domain", "Domain"],
  ["education", "Education & certification"],
];

export const isActive = (status: MatchStatus) => status === "QUEUED" || status === "RUNNING";

export const scoreJob = (jobId: string) =>
  apiFetch(`/jobs/${jobId}/score`, scoreResponseSchema, { method: "POST", body: "{}" });
export const getMatch = (id: string) => apiFetch(`/matches/${id}`, matchSchema);
export const latestMatchForJob = async (jobId: string) => {
  const matches = await apiFetch(`/matches?job_id=${jobId}&limit=1`, z.array(matchSchema));
  return matches[0] ?? null;
};
