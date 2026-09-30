"use client";

import { useEffect, useId, useRef, useState } from "react";

import { buttonClass, inputClass, primaryButtonClass } from "@/components/ui/styles";
import type { Company } from "@/lib/api/companies";

interface Props {
  company: Company;
  open: boolean;
  saving: boolean;
  error: string | null;
  onSave: (notes: string) => void;
  onClose: () => void;
}

export function NotesDialog({ company, open, saving, error, onSave, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  const [draft, setDraft] = useState(company.eures_notes ?? "");

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={`${id}-title`}
      onClose={onClose}
      className="m-auto w-full max-w-lg rounded border border-border bg-background p-0 text-foreground backdrop:bg-black/40"
    >
      <form
        method="dialog"
        className="space-y-3 p-4"
        onSubmit={(event) => {
          event.preventDefault();
          onSave(draft);
        }}
      >
        <h2 id={`${id}-title`} className="text-base font-semibold">
          EURES notes — {company.company_name}
        </h2>
        <label htmlFor={`${id}-notes`} className="sr-only">
          Notes
        </label>
        <textarea
          id={`${id}-notes`}
          value={draft}
          maxLength={5000}
          rows={5}
          onChange={(event) => setDraft(event.target.value)}
          className={`${inputClass} h-auto w-full py-1.5`}
          placeholder="e.g. Only sales roles on EURES; check careers page in March"
        />
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" className={buttonClass} onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className={primaryButtonClass} disabled={saving}>
            {saving ? "Saving…" : "Save notes"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
