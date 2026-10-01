"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState } from "react";

import { inputClass, primaryButtonClass } from "@/components/ui/styles";
import {
  ACCEPTED_RESUME_TYPES,
  MAX_RESUME_BYTES,
  uploadResume,
  type Resume,
} from "@/lib/api/resumes";

export function ResumeUpload({ onUploaded }: { onUploaded: (resume: Resume) => void }) {
  const id = useId();
  const client = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: () => uploadResume(file as File, name),
    onSuccess: (resume) => {
      void client.invalidateQueries({ queryKey: ["resumes"] });
      setFile(null);
      setName("");
      if (fileInput.current) fileInput.current.value = "";
      onUploaded(resume);
    },
  });

  const choose = (selected: File | null) => {
    upload.reset();
    setLocalError(null);
    if (selected && selected.size > MAX_RESUME_BYTES) {
      setLocalError("The file is larger than 10 MB");
      setFile(null);
      return;
    }
    setFile(selected);
  };

  const error = localError ?? (upload.isError ? upload.error.message : null);

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded border border-border p-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (file) upload.mutate();
      }}
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-file`} className="text-xs font-medium text-muted">
          Resume file (PDF, DOCX or TXT, max 10 MB)
        </label>
        <input
          ref={fileInput}
          id={`${id}-file`}
          type="file"
          accept={ACCEPTED_RESUME_TYPES}
          onChange={(event) => choose(event.target.files?.[0] ?? null)}
          className="text-sm file:mr-2 file:rounded file:border file:border-border file:bg-surface file:px-2 file:py-1 file:text-sm"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-name`} className="text-xs font-medium text-muted">
          Label (optional)
        </label>
        <input
          id={`${id}-name`}
          value={name}
          maxLength={120}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. ML engineer 2026"
          className={`${inputClass} w-56`}
        />
      </div>
      <button type="submit" className={primaryButtonClass} disabled={!file || upload.isPending}>
        {upload.isPending ? "Uploading…" : "Upload resume"}
      </button>
      {error && (
        <p role="alert" className="w-full text-sm text-danger">
          {error}
        </p>
      )}
    </form>
  );
}
