import { z } from "zod";

import { API_BASE_URL, apiFetch } from "./client";
import { runSchema, runStatusSchema } from "./match-runs";

export const SITES = ["indeed", "linkedin", "google"] as const;
export type Site = (typeof SITES)[number];
export const SITE_LABELS: Record<string, string> = {
  indeed: "Indeed Denmark",
  linkedin: "LinkedIn",
  google: "Google Jobs",
  eures: "EURES search",
  "eures companies": "EURES company scan",
  "job boards": "Job boards",
  scoring: "Scoring",
};

export const discoverySettingsSchema = z.object({
  search_terms: z.array(z.string()),
  location: z.string(),
  sites: z.array(z.string()),
  results_per_site: z.number().int(),
  hours_old: z.number().int(),
  eures_enabled: z.boolean(),
  eures_companies_per_run: z.number().int(),
  scrape_budget_minutes: z.number().int(),
  total_budget_minutes: z.number().int(),
  effective_terms: z.array(z.string()),
  jobspy_enabled: z.boolean(),
  eures_scraper_enabled: z.boolean(),
  eures_available: z.boolean(),
});
export type DiscoverySettings = z.infer<typeof discoverySettingsSchema>;
export type DiscoverySettingsUpdate = Partial<
  Pick<
    DiscoverySettings,
    | "search_terms"
    | "location"
    | "results_per_site"
    | "hours_old"
    | "eures_enabled"
    | "eures_companies_per_run"
    | "scrape_budget_minutes"
    | "total_budget_minutes"
  > & { sites: Site[] }
>;

const sourceEntrySchema = z.object({
  source: z.string(),
  term: z.string().nullable(),
  status: z.string(),
  message: z.string().nullable(),
  found: z.number().int(),
  created: z.number().int(),
  attached: z.number().int(),
  unchanged: z.number().int(),
  skipped: z.number().int(),
  linked_siri: z.number().int(),
  companies_scanned: z.number().int().optional(),
  companies_with_jobs: z.number().int().optional(),
  errors: z.number().int().optional(),
});
export type SourceEntry = z.infer<typeof sourceEntrySchema>;

export const discoveryPhaseSchema = z.enum(["QUEUED", "SCRAPING", "EURES", "SCORING", "FINISHED"]);

export const discoveryRunSchema = z.object({
  id: z.string(),
  trigger: z.enum(["manual", "scheduled"]),
  status: runStatusSchema,
  phase: discoveryPhaseSchema,
  settings: z.record(z.string(), z.unknown()),
  sources: z.array(sourceEntrySchema),
  new_jobs: z.array(z.object({ id: z.string(), title: z.string(), source: z.string() })),
  scoring: runSchema.nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  created_at: z.string(),
  started_at: z.string().nullable(),
  scrape_deadline: z.string().nullable(),
  deadline: z.string().nullable(),
  completed_at: z.string().nullable(),
});
export type DiscoveryRun = z.infer<typeof discoveryRunSchema>;

export const getDiscoverySettings = () => apiFetch("/discovery/settings", discoverySettingsSchema);
export const updateDiscoverySettings = (body: DiscoverySettingsUpdate) =>
  apiFetch("/discovery/settings", discoverySettingsSchema, {
    method: "PUT",
    body: JSON.stringify(body),
  });
export const startDiscovery = () =>
  apiFetch("/discovery-runs", discoveryRunSchema, { method: "POST", body: "{}" });
export const latestDiscoveryRun = async () =>
  (await apiFetch("/discovery-runs?limit=1", z.array(discoveryRunSchema)))[0] ?? null;
export const cancelDiscovery = (id: string) =>
  apiFetch(`/discovery-runs/${id}/cancel`, discoveryRunSchema, { method: "POST" });
export const discoveryEventsUrl = (id: string) =>
  `${API_BASE_URL}/api/v1/discovery-runs/${id}/events`;
