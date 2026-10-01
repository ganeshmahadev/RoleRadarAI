"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { buttonClass, inputClass, primaryButtonClass } from "@/components/ui/styles";
import { TagInput } from "@/components/ui/tag-input";
import {
  SITE_LABELS,
  SITES,
  updateDiscoverySettings,
  type DiscoverySettings,
  type Site,
} from "@/lib/api/discovery";

const NUMBERS = [
  ["results_per_site", "Results per board and term", 1, 100],
  ["hours_old", "Only jobs posted in the last (hours)", 1, 720],
  ["eures_companies_per_run", "SIRI companies scanned per run", 1, 982],
  ["scrape_budget_minutes", "Search time budget (min)", 1, 240],
  ["total_budget_minutes", "Total time budget incl. scoring (min)", 1, 600],
] as const;
type NumberKey = (typeof NUMBERS)[number][0];

type Draft = Pick<DiscoverySettings, "search_terms" | "location" | "eures_enabled"> & {
  sites: Site[];
} & Record<NumberKey, string>;

function toDraft(s: DiscoverySettings): Draft {
  return {
    search_terms: s.search_terms,
    location: s.location,
    eures_enabled: s.eures_enabled,
    sites: s.sites.filter((x): x is Site => (SITES as readonly string[]).includes(x)),
    ...(Object.fromEntries(NUMBERS.map(([k]) => [k, String(s[k])])) as Record<NumberKey, string>),
  };
}

function invalidNumber(value: string, min: number, max: number) {
  return !/^\d+$/.test(value) || Number(value) < min || Number(value) > max;
}

export function DiscoverySettingsForm({ settings }: { settings: DiscoverySettings }) {
  const id = useId();
  const client = useQueryClient();
  const [draft, setDraft] = useState<Draft>(() => toDraft(settings));
  const dirty = JSON.stringify(draft) !== JSON.stringify(toDraft(settings));
  const errors = NUMBERS.filter(([k, , min, max]) => invalidNumber(draft[k], min, max)).map(
    ([k]) => k,
  );
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  const save = useMutation({
    mutationFn: () =>
      updateDiscoverySettings({
        search_terms: draft.search_terms,
        location: draft.location,
        sites: draft.sites,
        eures_enabled: draft.eures_enabled,
        ...(Object.fromEntries(NUMBERS.map(([k]) => [k, Number(draft[k])])) as Record<
          NumberKey,
          number
        >),
      }),
    onSuccess: (saved) => {
      client.setQueryData(["discovery", "settings"], saved);
      setDraft(toDraft(saved));
    },
  });

  return (
    <form
      aria-labelledby={`${id}-title`}
      className="space-y-4 rounded border border-border p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!errors.length) save.mutate();
      }}
    >
      <h2 id={`${id}-title`} className="text-sm font-semibold">
        Search settings
      </h2>

      <TagInput
        label="Search terms"
        values={draft.search_terms}
        onChange={(v) => set("search_terms", v)}
        placeholder="e.g. Machine Learning Engineer"
        maxItems={20}
        hint={
          draft.search_terms.length
            ? "Press Enter or comma to add."
            : `Empty: uses your profile's target roles (${settings.effective_terms.join(", ") || "none set"}).`
        }
      />

      <div className="space-y-1">
        <label htmlFor={`${id}-location`} className="text-xs font-medium text-muted">
          Location
        </label>
        <input
          id={`${id}-location`}
          value={draft.location}
          maxLength={100}
          onChange={(e) => set("location", e.target.value)}
          className={`${inputClass} w-full`}
        />
      </div>

      <fieldset className="space-y-1">
        <legend className="text-xs font-medium text-muted">Sources</legend>
        <div className="flex flex-wrap gap-4 text-sm">
          {SITES.map((site) => (
            <label key={site} className="inline-flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={draft.sites.includes(site)}
                disabled={!settings.jobspy_enabled}
                onChange={(e) =>
                  set(
                    "sites",
                    e.target.checked
                      ? SITES.filter((s) => s === site || draft.sites.includes(s))
                      : draft.sites.filter((s) => s !== site),
                  )
                }
              />
              {SITE_LABELS[site]}
            </label>
          ))}
          <label className="inline-flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={draft.eures_enabled}
              disabled={!settings.eures_available}
              onChange={(e) => set("eures_enabled", e.target.checked)}
            />
            EURES (search + SIRI company scan)
          </label>
        </div>
        {(!settings.jobspy_enabled || !settings.eures_available) && (
          <p className="text-xs text-muted">
            {!settings.jobspy_enabled && "Job boards are off (DISCOVERY_JOBSPY_ENABLED). "}
            {!settings.eures_available && "EURES scan is off (EURES_SCRAPER_ENABLED). "}
            Turn them on in <code>.env</code> and restart the API and worker.
          </p>
        )}
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {NUMBERS.map(([key, label, min, max]) => {
          const invalid = errors.includes(key);
          return (
            <div key={key} className="space-y-1">
              <label htmlFor={`${id}-${key}`} className="text-xs font-medium text-muted">
                {label}
              </label>
              <input
                id={`${id}-${key}`}
                inputMode="numeric"
                value={draft[key]}
                onChange={(e) => set(key, e.target.value)}
                aria-invalid={invalid}
                aria-describedby={invalid ? `${id}-${key}-error` : undefined}
                className={`${inputClass} w-full`}
              />
              {invalid && (
                <p id={`${id}-${key}-error`} className="text-xs text-danger">
                  Whole number from {min} to {max}.
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          className={primaryButtonClass}
          disabled={!dirty || errors.length > 0 || save.isPending}
        >
          {save.isPending ? "Saving…" : "Save settings"}
        </button>
        {dirty && (
          <button type="button" className={buttonClass} onClick={() => setDraft(toDraft(settings))}>
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
