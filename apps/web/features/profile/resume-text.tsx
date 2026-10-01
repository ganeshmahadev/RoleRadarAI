"use client";

import { useQuery } from "@tanstack/react-query";

import { getResume } from "@/lib/api/resumes";

/** Extracted text exactly as stored: this is the evidence matching will use. */
export function ResumeText({ resumeId }: { resumeId: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["resumes", "detail", resumeId],
    queryFn: () => getResume(resumeId),
  });

  return (
    <section aria-labelledby="resume-text-title" className="space-y-2">
      <h2 id="resume-text-title" className="text-sm font-semibold">
        Extracted text
      </h2>
      {isPending && <div className="h-64 animate-pulse rounded border border-border bg-surface" />}
      {isError && (
        <p role="alert" className="text-sm text-danger">
          {error.message}
        </p>
      )}
      {data && (
        <>
          <p className="text-xs text-muted">
            {data.original_filename} · {data.text_chars.toLocaleString("en-GB")} characters · This
            text is what matching reads. If something is missing, fix the source file and upload it
            again.
          </p>
          <pre
            tabIndex={0}
            aria-label={`Extracted text of ${data.name}`}
            className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded border border-border p-3 font-sans text-sm leading-relaxed"
          >
            {data.raw_text}
          </pre>
        </>
      )}
    </section>
  );
}
