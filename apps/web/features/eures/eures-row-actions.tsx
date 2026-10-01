"use client";

import { useState } from "react";

import { PopoverMenu } from "@/components/ui/popover-menu";
import { buttonClass } from "@/components/ui/styles";
import { OpenEuresLink } from "@/features/companies/open-eures-link";
import { ImportJobDialog } from "@/features/jobs/import-job-dialog";
import type { Company } from "@/lib/api/companies";
import type { EuresAction } from "@/lib/api/eures";

import { NotesDialog } from "./notes-dialog";
import { useEuresMutations } from "./use-eures-mutations";

const COMPLETED = new Set(["CHECKED_NO_JOBS", "JOB_FOUND", "ERROR"]);
const small = `${buttonClass} h-7 px-2 text-xs`;
const menuItem =
  "block w-full rounded px-2 py-1.5 text-left text-sm hover:bg-surface disabled:opacity-50";

/** EURES workflow actions for one company (PRD §8, §24). Rare actions live under "More". */
export function EuresRowActions({ company }: { company: Company }) {
  const { action, notes } = useEuresMutations();
  const [dialog, setDialog] = useState<"notes" | "import" | null>(null);
  const pending = action.isPending && action.variables?.companyId === company.id;
  const completed = COMPLETED.has(company.eures_status);
  const run = (name: EuresAction) => action.mutate({ companyId: company.id, action: name });

  return (
    <>
      <OpenEuresLink company={company} onOpen={() => run("eures-opened")} />
      <button
        type="button"
        className={small}
        onClick={() => setDialog("import")}
        aria-label={`Import a job for ${company.company_name}`}
      >
        Import job
      </button>
      {completed ? (
        <button
          type="button"
          className={small}
          disabled={pending}
          onClick={() => run("reset-eures")}
          aria-label={`Reset EURES status for ${company.company_name}`}
        >
          Reset
        </button>
      ) : (
        <button
          type="button"
          className={small}
          disabled={pending}
          onClick={() => run("mark-no-jobs")}
          aria-label={`Mark ${company.company_name} as no relevant jobs`}
        >
          No relevant jobs
        </button>
      )}
      <PopoverMenu
        label="More ▾"
        triggerClassName={small}
        triggerAriaLabel={`More actions for ${company.company_name}`}
      >
        <button
          type="button"
          className={menuItem}
          onClick={() => {
            notes.reset();
            setDialog("notes");
          }}
        >
          {company.eures_notes ? "Edit note" : "Add note"}
        </button>
        {!completed && (
          <button
            type="button"
            className={menuItem}
            disabled={pending}
            onClick={() => {
              run("mark-eures-error");
            }}
          >
            Mark EURES error
          </button>
        )}
        {company.eures_status === "OPENED" && (
          <button
            type="button"
            className={menuItem}
            disabled={pending}
            onClick={() => {
              run("reset-eures");
            }}
          >
            Reset to not checked
          </button>
        )}
      </PopoverMenu>
      {action.isError && action.variables?.companyId === company.id && (
        <span role="alert" className="text-xs text-danger">
          {action.error.message}
        </span>
      )}
      {dialog === "notes" && (
        <NotesDialog
          company={company}
          open
          saving={notes.isPending}
          error={notes.isError ? notes.error.message : null}
          onClose={() => setDialog(null)}
          onSave={(value) =>
            notes.mutate(
              { companyId: company.id, notes: value },
              { onSuccess: () => setDialog(null) },
            )
          }
        />
      )}
      {dialog === "import" && (
        <ImportJobDialog company={company} open onClose={() => setDialog(null)} />
      )}
    </>
  );
}
