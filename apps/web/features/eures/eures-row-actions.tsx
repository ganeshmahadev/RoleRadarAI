"use client";

import { useState } from "react";

import { buttonClass } from "@/components/ui/styles";
import { OpenEuresLink } from "@/features/companies/open-eures-link";
import type { Company } from "@/lib/api/companies";

import { NotesDialog } from "./notes-dialog";
import { useEuresMutations } from "./use-eures-mutations";

const COMPLETED = new Set(["CHECKED_NO_JOBS", "JOB_FOUND", "ERROR"]);
const small = `${buttonClass} h-7 px-2 text-xs`;

/** EURES workflow actions for one company (PRD §8, §24). */
export function EuresRowActions({ company }: { company: Company }) {
  const { action, notes } = useEuresMutations();
  const [notesOpen, setNotesOpen] = useState(false);
  const pending = action.isPending && action.variables?.companyId === company.id;
  const run = (name: Parameters<typeof action.mutate>[0]["action"]) =>
    action.mutate({ companyId: company.id, action: name });

  return (
    <>
      <OpenEuresLink company={company} onOpen={() => run("eures-opened")} />
      {COMPLETED.has(company.eures_status) ? (
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
        <>
          <button
            type="button"
            className={small}
            disabled={pending}
            onClick={() => run("mark-no-jobs")}
            aria-label={`Mark ${company.company_name} as no relevant jobs`}
          >
            No relevant jobs
          </button>
          <button
            type="button"
            className={small}
            disabled={pending}
            onClick={() => run("mark-eures-error")}
            aria-label={`Mark EURES error for ${company.company_name}`}
          >
            Error
          </button>
        </>
      )}
      <button
        type="button"
        className={small}
        onClick={() => {
          notes.reset();
          setNotesOpen(true);
        }}
        aria-label={`${company.eures_notes ? "Edit" : "Add"} notes for ${company.company_name}`}
      >
        {company.eures_notes ? "Edit note" : "Add note"}
      </button>
      {action.isError && action.variables?.companyId === company.id && (
        <span role="alert" className="text-xs text-danger">
          {action.error.message}
        </span>
      )}
      {notesOpen && (
        <NotesDialog
          company={company}
          open={notesOpen}
          saving={notes.isPending}
          error={notes.isError ? notes.error.message : null}
          onClose={() => setNotesOpen(false)}
          onSave={(value) =>
            notes.mutate(
              { companyId: company.id, notes: value },
              { onSuccess: () => setNotesOpen(false) },
            )
          }
        />
      )}
    </>
  );
}
