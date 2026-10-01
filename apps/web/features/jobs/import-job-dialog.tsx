"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { buttonClass, inputClass, primaryButtonClass } from "@/components/ui/styles";
import { errorCode } from "@/lib/api/client";
import type { Company } from "@/lib/api/companies";
import {
  IMPORT_OUTCOME_MESSAGES,
  MANUAL_PASTE_CODES,
  importJobText,
  importJobUrl,
  type ImportResponse,
} from "@/lib/api/jobs";

interface Props {
  /** When importing from a company's queue row, the job is linked and the company becomes "Job found". */
  company?: Company | null;
  open: boolean;
  onClose: () => void;
}

type Mode = "url" | "paste";

export function ImportJobDialog({ company, open, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  const client = useQueryClient();
  const [mode, setMode] = useState<Mode>("url");
  const [url, setUrl] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const [manual, setManual] = useState({
    title: "",
    description: "",
    location: "",
    employer_name: "",
    source_url: "",
  });
  const [result, setResult] = useState<ImportResponse | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const onSuccess = (response: ImportResponse) => setResult(response);

  /**
   * Lists refresh only when the dialog closes: refreshing earlier would move the EURES queue
   * to the next company (unmounting this dialog) before the result is visible.
   */
  const close = () => {
    if (result) {
      void client.invalidateQueries({ queryKey: ["companies"] });
      void client.invalidateQueries({ queryKey: ["eures"] });
      void client.invalidateQueries({ queryKey: ["jobs"] });
    }
    onClose();
  };

  const byUrl = useMutation({
    mutationFn: () => importJobUrl(url, company?.id),
    onSuccess,
    onError: (error) => {
      const code = errorCode(error);
      if (code && MANUAL_PASTE_CODES.has(code)) {
        setHint(error.message);
        setManual((m) => ({ ...m, source_url: m.source_url || url }));
        setMode("paste");
      }
    },
  });
  const byText = useMutation({
    mutationFn: () =>
      importJobText({
        title: manual.title,
        description: manual.description,
        location: manual.location || undefined,
        employer_name: manual.employer_name || undefined,
        source_url: manual.source_url || undefined,
        company_id: company?.id,
      }),
    onSuccess,
  });
  const active = mode === "url" ? byUrl : byText;
  const showUrlError = mode === "url" && byUrl.isError;

  return (
    <dialog
      ref={ref}
      aria-labelledby={`${id}-title`}
      onClose={close}
      className="m-auto w-full max-w-xl rounded border border-border bg-background p-0 text-foreground backdrop:bg-black/40"
    >
      <div className="space-y-4 p-4">
        <h2 id={`${id}-title`} className="text-base font-semibold">
          Import job{company ? ` — ${company.company_name}` : ""}
        </h2>

        {result ? (
          <div className="space-y-3" role="status">
            <p className="text-sm">{IMPORT_OUTCOME_MESSAGES[result.outcome]}</p>
            <p className="text-sm">
              <span className="font-medium">{result.job.title}</span>
              {result.job.location && <span className="text-muted"> · {result.job.location}</span>}
            </p>
            <div className="flex justify-end gap-2">
              <button type="button" className={buttonClass} onClick={close}>
                Close
              </button>
              <Link href={`/jobs/${result.job.id}`} className={primaryButtonClass} onClick={close}>
                View job
              </Link>
            </div>
          </div>
        ) : (
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              active.mutate();
            }}
          >
            <div role="tablist" aria-label="Import method" className="flex gap-1 text-sm">
              {(["url", "paste"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => setMode(m)}
                  className={`rounded px-2 py-1 ${mode === m ? "bg-surface font-medium" : "text-muted"}`}
                >
                  {m === "url" ? "From URL" : "Paste description"}
                </button>
              ))}
            </div>

            {mode === "url" ? (
              <div className="space-y-1">
                <label htmlFor={`${id}-url`} className="text-xs font-medium text-muted">
                  Original employer or ATS job URL (not the EURES page)
                </label>
                <input
                  id={`${id}-url`}
                  type="url"
                  required
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://company.com/jobs/123"
                  className={`${inputClass} w-full`}
                />
              </div>
            ) : (
              <div className="space-y-2">
                {hint && (
                  <p className="rounded border border-warning/40 p-2 text-sm text-warning">
                    {hint}
                  </p>
                )}
                <Field id={`${id}-title-in`} label="Job title" required>
                  <input
                    id={`${id}-title-in`}
                    required
                    minLength={2}
                    maxLength={300}
                    value={manual.title}
                    onChange={(e) => setManual({ ...manual, title: e.target.value })}
                    className={`${inputClass} w-full`}
                  />
                </Field>
                <div className="grid grid-cols-2 gap-2">
                  <Field id={`${id}-loc`} label="Location">
                    <input
                      id={`${id}-loc`}
                      value={manual.location}
                      onChange={(e) => setManual({ ...manual, location: e.target.value })}
                      className={`${inputClass} w-full`}
                    />
                  </Field>
                  <Field id={`${id}-emp`} label="Employer">
                    <input
                      id={`${id}-emp`}
                      value={manual.employer_name}
                      placeholder={company?.company_name}
                      onChange={(e) => setManual({ ...manual, employer_name: e.target.value })}
                      className={`${inputClass} w-full`}
                    />
                  </Field>
                </div>
                <Field id={`${id}-src`} label="Original posting URL (reference only, not fetched)">
                  <input
                    id={`${id}-src`}
                    type="url"
                    value={manual.source_url}
                    onChange={(e) => setManual({ ...manual, source_url: e.target.value })}
                    className={`${inputClass} w-full`}
                  />
                </Field>
                <Field id={`${id}-desc`} label="Job description" required>
                  <textarea
                    id={`${id}-desc`}
                    required
                    minLength={50}
                    rows={8}
                    value={manual.description}
                    onChange={(e) => setManual({ ...manual, description: e.target.value })}
                    className={`${inputClass} h-auto w-full py-1.5`}
                  />
                </Field>
              </div>
            )}

            {(showUrlError || (mode === "paste" && byText.isError)) && (
              <p role="alert" className="text-sm text-danger">
                {(mode === "url" ? byUrl.error : byText.error)?.message}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <button type="button" className={buttonClass} onClick={close}>
                Cancel
              </button>
              <button type="submit" className={primaryButtonClass} disabled={active.isPending}>
                {active.isPending ? "Importing…" : "Import"}
              </button>
            </div>
          </form>
        )}
      </div>
    </dialog>
  );
}

function Field({
  id,
  label,
  required,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs font-medium text-muted">
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {children}
    </div>
  );
}
