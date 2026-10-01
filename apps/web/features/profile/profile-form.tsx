"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { buttonClass, inputClass, primaryButtonClass } from "@/components/ui/styles";
import { TagInput } from "@/components/ui/tag-input";
import {
  CEFR_LEVELS,
  getProfile,
  REMOTE_LABELS,
  REMOTE_PREFERENCES,
  updateProfile,
  type LanguageEntry,
  type Profile,
  type ProfileUpdate,
} from "@/lib/api/resumes";

type Draft = Required<Omit<ProfileUpdate, "years_experience">> & { years_experience: string };

const LIST_FIELDS = [
  ["target_roles", "Target roles", "e.g. Machine Learning Engineer"],
  ["skills", "Skills", "e.g. Python, PyTorch, FastAPI"],
  ["industries", "Preferred industries", "e.g. Fintech, Energy"],
  ["education", "Education", "e.g. MSc Computer Science, Aarhus University"],
  ["certifications", "Certifications", "e.g. AWS Solutions Architect"],
  ["preferred_locations", "Preferred locations", "e.g. Copenhagen"],
  ["work_authorization", "Work authorization", "e.g. Needs Fast-track work permit"],
] as const;

function toDraft(profile: Profile): Draft {
  return {
    target_roles: profile.target_roles,
    skills: profile.skills,
    industries: profile.industries,
    education: profile.education,
    certifications: profile.certifications,
    languages: profile.languages,
    preferred_locations: profile.preferred_locations,
    remote_preference: profile.remote_preference,
    work_authorization: profile.work_authorization,
    years_experience: profile.years_experience ?? "",
  };
}

function toUpdate(draft: Draft): ProfileUpdate {
  const years = draft.years_experience.trim();
  return {
    ...draft,
    languages: draft.languages.filter((l) => l.language.trim()),
    years_experience: years === "" ? null : Number(years),
  };
}

export function ProfileForm({ resumeId, resumeName }: { resumeId: string; resumeName: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["resumes", "profile", resumeId],
    queryFn: () => getProfile(resumeId),
  });
  if (isPending)
    return <div className="h-96 animate-pulse rounded border border-border bg-surface" />;
  if (isError)
    return (
      <p role="alert" className="text-sm text-danger">
        {error.message}
      </p>
    );
  // Keyed by resume, not by updated_at: remounting after a save would hide the "Saved" status.
  return <ProfileEditor key={data.resume_id} profile={data} resumeName={resumeName} />;
}

function ProfileEditor({ profile, resumeName }: { profile: Profile; resumeName: string }) {
  const id = useId();
  const client = useQueryClient();
  const [draft, setDraft] = useState<Draft>(() => toDraft(profile));
  const dirty = JSON.stringify(draft) !== JSON.stringify(toDraft(profile));
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  const save = useMutation({
    mutationFn: () => updateProfile(profile.resume_id, toUpdate(draft)),
    onSuccess: (saved) => {
      client.setQueryData(["resumes", "profile", profile.resume_id], saved);
      setDraft(toDraft(saved)); // reflect server-side cleanup (trimmed, de-duplicated values)
    },
  });
  const years = draft.years_experience.trim();
  const yearsInvalid = years !== "" && (!/^\d{1,2}(\.\d)?$/.test(years) || Number(years) > 60);

  return (
    <form
      aria-labelledby={`${id}-title`}
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!yearsInvalid) save.mutate();
      }}
    >
      <div>
        <h2 id={`${id}-title`} className="text-sm font-semibold">
          Candidate profile
        </h2>
        <p className="text-xs text-muted">
          For “{resumeName}”. You enter these yourself; matching uses them together with the resume
          text. Nothing here is filled in by AI.
        </p>
      </div>

      {LIST_FIELDS.slice(0, 2).map(([key, label, placeholder]) => (
        <TagInput
          key={key}
          label={label}
          values={draft[key]}
          onChange={(values) => set(key, values)}
          placeholder={placeholder}
          hint="Press Enter or comma to add."
        />
      ))}

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label htmlFor={`${id}-years`} className="text-xs font-medium text-muted">
            Years of experience
          </label>
          <input
            id={`${id}-years`}
            inputMode="decimal"
            value={draft.years_experience}
            onChange={(event) => set("years_experience", event.target.value)}
            aria-invalid={yearsInvalid}
            aria-describedby={yearsInvalid ? `${id}-years-error` : undefined}
            placeholder="e.g. 5.5"
            className={`${inputClass} w-full`}
          />
          {yearsInvalid && (
            <p id={`${id}-years-error`} className="text-xs text-danger">
              Use a number from 0 to 60 with at most one decimal.
            </p>
          )}
        </div>
        <div className="space-y-1">
          <label htmlFor={`${id}-remote`} className="text-xs font-medium text-muted">
            Remote preference
          </label>
          <select
            id={`${id}-remote`}
            value={draft.remote_preference ?? ""}
            onChange={(event) =>
              set("remote_preference", (event.target.value || null) as Draft["remote_preference"])
            }
            className={`${inputClass} w-full`}
          >
            <option value="">Not set</option>
            {REMOTE_PREFERENCES.map((value) => (
              <option key={value} value={value}>
                {REMOTE_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
      </div>

      <LanguagesEditor value={draft.languages} onChange={(v) => set("languages", v)} />

      {LIST_FIELDS.slice(2).map(([key, label, placeholder]) => (
        <TagInput
          key={key}
          label={label}
          values={draft[key]}
          onChange={(values) => set(key, values)}
          placeholder={placeholder}
        />
      ))}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          className={primaryButtonClass}
          disabled={!dirty || yearsInvalid || save.isPending}
        >
          {save.isPending ? "Saving…" : "Save profile"}
        </button>
        {dirty && (
          <button type="button" className={buttonClass} onClick={() => setDraft(toDraft(profile))}>
            Discard changes
          </button>
        )}
        <p role="status" className="text-sm">
          {save.isError ? (
            <span className="text-danger">{save.error.message}</span>
          ) : save.isSuccess && !dirty ? (
            <span className="text-success">Saved</span>
          ) : null}
        </p>
      </div>
    </form>
  );
}

function LanguagesEditor({
  value,
  onChange,
}: {
  value: LanguageEntry[];
  onChange: (value: LanguageEntry[]) => void;
}) {
  const id = useId();
  const update = (index: number, entry: LanguageEntry) =>
    onChange(value.map((current, i) => (i === index ? entry : current)));
  return (
    <fieldset className="space-y-2">
      <legend className="text-xs font-medium text-muted">Languages (CEFR level)</legend>
      {value.map((entry, index) => (
        <div key={index} className="flex items-center gap-2">
          <label htmlFor={`${id}-lang-${index}`} className="sr-only">
            Language {index + 1}
          </label>
          <input
            id={`${id}-lang-${index}`}
            value={entry.language}
            maxLength={60}
            placeholder="e.g. Danish"
            onChange={(event) => update(index, { ...entry, language: event.target.value })}
            className={`${inputClass} flex-1`}
          />
          <label htmlFor={`${id}-level-${index}`} className="sr-only">
            Level for language {index + 1}
          </label>
          <select
            id={`${id}-level-${index}`}
            value={entry.level}
            onChange={(event) =>
              update(index, { ...entry, level: event.target.value as LanguageEntry["level"] })
            }
            className={inputClass}
          >
            {CEFR_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={`${buttonClass} h-8 px-2`}
            onClick={() => onChange(value.filter((_, i) => i !== index))}
            aria-label={`Remove language ${entry.language || index + 1}`}
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        className={`${buttonClass} h-7 px-2 text-xs`}
        disabled={value.length >= 20}
        onClick={() => onChange([...value, { language: "", level: "B2" }])}
      >
        Add language
      </button>
    </fieldset>
  );
}
