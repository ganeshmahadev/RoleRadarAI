import { z } from "zod";

import { apiFetch } from "./client";

export const EURES_STATUSES = [
  "NOT_CHECKED",
  "OPENED",
  "CHECKED_NO_JOBS",
  "JOB_FOUND",
  "ERROR",
] as const;
export const euresStatusSchema = z.enum(EURES_STATUSES);
export type EuresStatus = z.infer<typeof euresStatusSchema>;

/** UI labels (PRD §8: CHECKED_NO_JOBS is shown as "No relevant jobs"). */
export const EURES_STATUS_LABELS: Record<EuresStatus, string> = {
  NOT_CHECKED: "Not checked",
  OPENED: "Opened",
  CHECKED_NO_JOBS: "No relevant jobs",
  JOB_FOUND: "Job found",
  ERROR: "Error",
};

export const companySchema = z.object({
  id: z.string().uuid(),
  company_name: z.string(),
  normalized_name: z.string(),
  cvr: z.string(), // CVR is text; never coerce to a number.
  source_position: z.number().int().nullable(),
  siri_certified: z.boolean(),
  siri_source_url: z.string().nullable(),
  siri_last_seen_at: z.string().nullable(),
  eures_search_url: z.string().url(),
  eures_status: euresStatusSchema,
  eures_last_checked_at: z.string().nullable(),
  eures_notes: z.string().nullable(),
  /** "user" or "scan" (automated discovery, PRD §84). */
  eures_checked_by: z.string().nullable().default(null),
  website_url: z.string().nullable(),
  careers_url: z.string().nullable(),
  ats_provider: z.string().nullable(),
  active: z.boolean(),
  jobs_count: z.number().int(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Company = z.infer<typeof companySchema>;

export const companyPageSchema = z.object({
  items: z.array(companySchema),
  total: z.number().int(),
  page: z.number().int(),
  page_size: z.number().int(),
});
export type CompanyPage = z.infer<typeof companyPageSchema>;

/** "unchecked" = NOT_CHECKED or OPENED; "checked" = any outcome (PRD §8). */
export type StatusFilter = "all" | "unchecked" | "checked" | EuresStatus;
export type CompanySort = "position" | "name" | "last_checked";

export interface CompanyQuery {
  q: string;
  status: StatusFilter;
  siriOnly: boolean;
  hasJobs: boolean;
  sort: CompanySort;
  page: number;
  pageSize: number;
}

export const DEFAULT_COMPANY_QUERY: CompanyQuery = {
  q: "",
  status: "all",
  siriOnly: false,
  hasJobs: false,
  sort: "position",
  page: 1,
  pageSize: 50,
};

export function toApiParams(query: CompanyQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (query.q.trim()) params.set("q", query.q.trim());
  if (query.status === "checked") params.set("checked", "true");
  else if (query.status === "unchecked") params.set("checked", "false");
  else if (query.status !== "all") params.set("eures_status", query.status);
  if (query.siriOnly) params.set("siri_certified", "true");
  if (query.hasJobs) params.set("has_jobs", "true");
  params.set("sort", query.sort);
  params.set("page", String(query.page));
  params.set("page_size", String(query.pageSize));
  return params;
}

export const listCompanies = (query: CompanyQuery) =>
  apiFetch(`/companies?${toApiParams(query)}`, companyPageSchema);
