import { z } from "zod";

import { apiFetch } from "./client";

export const resumeSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  original_filename: z.string(),
  mime_type: z.string(),
  size_bytes: z.number().int(),
  text_hash: z.string(),
  text_chars: z.number().int(),
  is_primary: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type ResumeSummary = z.infer<typeof resumeSummarySchema>;

export const resumeSchema = resumeSummarySchema.extend({ raw_text: z.string() });
export type Resume = z.infer<typeof resumeSchema>;

export const CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2", "Native"] as const;
export const REMOTE_PREFERENCES = ["onsite", "hybrid", "remote", "any"] as const;
export const REMOTE_LABELS: Record<(typeof REMOTE_PREFERENCES)[number], string> = {
  onsite: "On-site",
  hybrid: "Hybrid",
  remote: "Remote",
  any: "Any",
};

const languageSchema = z.object({ language: z.string(), level: z.enum(CEFR_LEVELS) });
export type LanguageEntry = z.infer<typeof languageSchema>;

export const profileSchema = z.object({
  id: z.string(),
  resume_id: z.string(),
  target_roles: z.array(z.string()),
  skills: z.array(z.string()),
  years_experience: z.string().nullable(), // Decimal serialized as a string
  industries: z.array(z.string()),
  education: z.array(z.string()),
  certifications: z.array(z.string()),
  languages: z.array(languageSchema),
  preferred_locations: z.array(z.string()),
  remote_preference: z.enum(REMOTE_PREFERENCES).nullable(),
  work_authorization: z.array(z.string()),
  updated_at: z.string(),
});
export type Profile = z.infer<typeof profileSchema>;

export type ProfileUpdate = Partial<
  Omit<Profile, "id" | "resume_id" | "updated_at" | "years_experience">
> & { years_experience?: number | null };

export const ACCEPTED_RESUME_TYPES = ".pdf,.docx,.txt";
export const MAX_RESUME_BYTES = 10 * 1024 * 1024;

export const listResumes = () => apiFetch("/resumes", z.array(resumeSummarySchema));
export const getResume = (id: string) => apiFetch(`/resumes/${id}`, resumeSchema);

export function uploadResume(file: File, name?: string) {
  const form = new FormData();
  form.append("file", file);
  if (name?.trim()) form.append("name", name.trim());
  return apiFetch("/resumes", resumeSchema, { method: "POST", body: form });
}

export const setPrimaryResume = (id: string) =>
  apiFetch(`/resumes/${id}/set-primary`, resumeSummarySchema, { method: "POST" });
export const deleteResume = (id: string) =>
  apiFetch(`/resumes/${id}`, z.null(), { method: "DELETE" });

export const getProfile = (resumeId: string) =>
  apiFetch(`/resumes/${resumeId}/profile`, profileSchema);
export const updateProfile = (resumeId: string, changes: ProfileUpdate) =>
  apiFetch(`/resumes/${resumeId}/profile`, profileSchema, {
    method: "PATCH",
    body: JSON.stringify(changes),
  });
