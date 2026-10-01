import { z } from "zod";

import { apiFetch } from "./client";

export const SOURCE_TYPE_LABELS = {
  jsonld: "Employer page (JSON-LD)",
  greenhouse: "Greenhouse",
  lever: "Lever",
  ashby: "Ashby",
  generic_html: "Employer page",
  manual: "Pasted manually",
} as const;
export const sourceTypeSchema = z.enum([
  "jsonld",
  "greenhouse",
  "lever",
  "ashby",
  "generic_html",
  "manual",
]);
export type SourceType = z.infer<typeof sourceTypeSchema>;

const companyRefSchema = z.object({ id: z.string(), company_name: z.string(), cvr: z.string() });

export const jobSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  employer_name: z.string().nullable(),
  company: companyRefSchema.nullable(),
  location: z.string().nullable(),
  source_type: sourceTypeSchema,
  source_url: z.string().nullable(),
  published_at: z.string().nullable(),
  created_at: z.string(),
  source_update_pending: z.boolean(),
  status: z.enum(["NEW", "SAVED", "IGNORED"]),
});
export type JobSummary = z.infer<typeof jobSummarySchema>;
export type JobStatus = JobSummary["status"];
export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  NEW: "New",
  SAVED: "Saved",
  IGNORED: "Ignored",
};

export const matchSummarySchema = z.object({
  id: z.string(),
  overall_score: z.number(),
  category: z.string(),
  hard_blocker: z.boolean(),
  missing_requirements: z.array(z.string()),
  uncertain_requirements: z.array(z.string()),
  completed_at: z.string().nullable(),
});
export type MatchSummary = z.infer<typeof matchSummarySchema>;

export const jobListItemSchema = jobSummarySchema.extend({
  match: matchSummarySchema.nullable(),
  match_outdated: z.boolean(),
  scoring: z.boolean(),
});
export type JobListItem = z.infer<typeof jobListItemSchema>;

export const jobSourceSchema = z.object({
  id: z.string(),
  source_type: sourceTypeSchema,
  source_url: z.string(),
  final_url: z.string().nullable(),
  status: z.enum(["ACCEPTED", "PENDING", "REJECTED"]),
  content_hash: z.string(),
  fetched_at: z.string(),
  normalized: z.record(z.string(), z.unknown()),
});
export type JobSource = z.infer<typeof jobSourceSchema>;

export const jobSchema = jobSummarySchema.extend({
  description: z.string(),
  country: z.string().nullable(),
  city: z.string().nullable(),
  employment_type: z.string().nullable(),
  workplace_type: z.string().nullable(),
  external_job_id: z.string().nullable(),
  apply_url: z.string().nullable(),
  expires_at: z.string().nullable(),
  content_hash: z.string(),
  updated_at: z.string(),
  sources: z.array(jobSourceSchema),
});
export type Job = z.infer<typeof jobSchema>;

export const importOutcomeSchema = z.enum([
  "created",
  "attached_source",
  "unchanged",
  "update_pending",
]);
export type ImportOutcome = z.infer<typeof importOutcomeSchema>;
export const importResponseSchema = z.object({ outcome: importOutcomeSchema, job: jobSchema });
export type ImportResponse = z.infer<typeof importResponseSchema>;

export const IMPORT_OUTCOME_MESSAGES: Record<ImportOutcome, string> = {
  created: "Imported a new job.",
  attached_source: "This vacancy was already stored; the new source was added to it.",
  unchanged: "Already imported — nothing changed.",
  update_pending: "The posting changed since it was imported. Review the update on the job page.",
};

/** Import errors where pasting the description is the way forward. */
export const MANUAL_PASTE_CODES = new Set([
  "ROBOTS_DISALLOWED",
  "EXTRACTION_FAILED",
  "UNSUPPORTED_SOURCE",
  "RESPONSE_TOO_LARGE",
]);

export const jobPageSchema = z.object({
  items: z.array(jobListItemSchema),
  total: z.number().int(),
  page: z.number().int(),
  page_size: z.number().int(),
});

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const importJobUrl = (url: string, companyId?: string) =>
  apiFetch("/jobs/import-url", importResponseSchema, json({ url, company_id: companyId }));

export interface ManualJobInput {
  title: string;
  description: string;
  employer_name?: string;
  location?: string;
  source_url?: string;
  company_id?: string;
}

export const importJobText = (input: ManualJobInput) =>
  apiFetch("/jobs/import-text", importResponseSchema, json(input));

export type JobSort = "match" | "newest" | "company" | "title";
export type BlockedMode = "last" | "mixed" | "exclude";
export type StatusView = "active" | "all" | JobStatus;

export interface JobQuery {
  q: string;
  location: string;
  companyId: string;
  source: SourceType | "";
  status: StatusView;
  siriOnly: boolean;
  scoredOnly: boolean;
  minScore: number | null;
  category: string;
  blocked: BlockedMode;
  sort: JobSort;
  page: number;
  pageSize: number;
}

export const DEFAULT_JOB_QUERY: JobQuery = {
  q: "",
  location: "",
  companyId: "",
  source: "",
  status: "active",
  siriOnly: false,
  scoredOnly: false,
  minScore: null,
  category: "",
  blocked: "last",
  sort: "newest",
  page: 1,
  pageSize: 50,
};

export function toJobApiParams(query: JobQuery): URLSearchParams {
  const params = new URLSearchParams({
    sort: query.sort,
    blocked: query.blocked,
    page: String(query.page),
    page_size: String(query.pageSize),
  });
  if (query.q.trim()) params.set("q", query.q.trim());
  if (query.location.trim()) params.set("location", query.location.trim());
  if (query.companyId) params.set("company_id", query.companyId);
  if (query.source) params.set("source_type", query.source);
  if (query.status === "all")
    for (const s of ["NEW", "SAVED", "IGNORED"]) params.append("status", s);
  else if (query.status !== "active") params.set("status", query.status);
  if (query.siriOnly) params.set("siri_only", "true");
  if (query.scoredOnly) params.set("scored", "true");
  if (query.minScore !== null) params.set("min_score", String(query.minScore));
  if (query.category) params.set("category", query.category);
  return params;
}

export const listJobs = (query: JobQuery) =>
  apiFetch(`/jobs?${toJobApiParams(query)}`, jobPageSchema);

export const countJobs = (params: Record<string, string>) =>
  apiFetch(`/jobs?${new URLSearchParams({ ...params, page_size: "1" })}`, jobPageSchema).then(
    (page) => page.total,
  );

export const updateJobStatus = (id: string, status: JobStatus) =>
  apiFetch(`/jobs/${id}`, jobSchema, { method: "PATCH", body: JSON.stringify({ status }) });

export const getJob = (id: string) => apiFetch(`/jobs/${id}`, jobSchema);

export const reviewSource = (jobId: string, sourceId: string, action: "accept" | "reject") =>
  apiFetch(`/jobs/${jobId}/sources/${sourceId}/${action}`, jobSchema, { method: "POST" });

export const deleteJob = (id: string) => apiFetch(`/jobs/${id}`, z.null(), { method: "DELETE" });
