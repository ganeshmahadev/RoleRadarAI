"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { primaryButtonClass } from "@/components/ui/styles";
import { getDiscoverySettings, startDiscovery } from "@/lib/api/discovery";
import { isRunActive } from "@/lib/api/match-runs";

import { DiscoveryRunPanel } from "./discovery-run-panel";
import { DiscoverySettingsForm } from "./discovery-settings-form";
import { LATEST_DISCOVERY_KEY, useLatestDiscovery } from "./use-discovery-run";

export function DiscoverView() {
  const client = useQueryClient();
  const settings = useQuery({ queryKey: ["discovery", "settings"], queryFn: getDiscoverySettings });
  const latest = useLatestDiscovery();
  const run = latest.data;
  const active = run ? isRunActive(run.status) : false;
  const start = useMutation({
    mutationFn: startDiscovery,
    onSuccess: (created) => client.setQueryData(LATEST_DISCOVERY_KEY, created),
  });

  if (settings.isPending || latest.isPending)
    return <div className="h-64 animate-pulse rounded border border-border bg-surface" />;
  if (settings.isError || latest.isError)
    return (
      <p role="alert" className="text-sm text-danger">
        {(settings.error ?? latest.error)?.message}
      </p>
    );

  const s = settings.data;
  const enabled = s.jobspy_enabled || (s.eures_available && s.eures_enabled);
  const noTerms = s.effective_terms.length === 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className={primaryButtonClass}
          disabled={active || start.isPending || !enabled || noTerms}
          onClick={() => start.mutate()}
        >
          {active ? "Search running…" : start.isPending ? "Starting…" : "Search now"}
        </button>
        <p className="text-xs text-muted">
          {!enabled
            ? "Automated search is off. Turn it on in .env (see below)."
            : noTerms
              ? "Add search terms below, or target roles in your profile."
              : `Searches for ${s.effective_terms.join(", ")} in ${s.location}, then scores the relevant jobs for up to ${s.total_budget_minutes} min.`}
        </p>
      </div>
      {start.isError && (
        <p role="alert" className="text-sm text-danger">
          {start.error.message}
        </p>
      )}

      {run ? (
        <DiscoveryRunPanel run={run} />
      ) : (
        <p className="text-sm text-muted">No searches yet.</p>
      )}

      <DiscoverySettingsForm settings={s} />
    </div>
  );
}
