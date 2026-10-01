"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { buttonClass } from "@/components/ui/styles";
import { deleteResume, setPrimaryResume, type ResumeSummary } from "@/lib/api/resumes";
import { formatDateTime } from "@/lib/format";

const small = `${buttonClass} h-7 px-2 text-xs`;

interface Props {
  resumes: ResumeSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function ResumeList({ resumes, selectedId, onSelect }: Props) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ["resumes"] });
  const primary = useMutation({ mutationFn: setPrimaryResume, onSuccess: refresh });
  const remove = useMutation({ mutationFn: deleteResume, onSuccess: refresh });
  const error = primary.error ?? remove.error;

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded border border-border">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">Uploaded resumes</caption>
          <thead className="bg-surface text-left text-xs text-muted">
            <tr>
              {["Resume", "File", "Uploaded", "Text", "Actions"].map((c) => (
                <th key={c} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {resumes.map((resume) => {
              const selected = resume.id === selectedId;
              return (
                <tr
                  key={resume.id}
                  aria-current={selected ? "true" : undefined}
                  className={`border-t border-border ${selected ? "bg-surface" : ""}`}
                >
                  <th scope="row" className="px-3 py-2 text-left font-medium">
                    {resume.name}
                    {resume.is_primary && (
                      <span className="ml-2 rounded border border-success/40 px-1 text-xs font-normal text-success">
                        Primary
                      </span>
                    )}
                  </th>
                  <td className="px-3 py-2 text-muted">{resume.original_filename}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-muted">
                    {formatDateTime(resume.created_at)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums text-muted">
                    {resume.text_chars.toLocaleString("en-GB")} chars
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2 whitespace-nowrap">
                      <button
                        type="button"
                        className={small}
                        disabled={selected}
                        onClick={() => onSelect(resume.id)}
                        aria-label={`View ${resume.name}`}
                      >
                        {selected ? "Viewing" : "View"}
                      </button>
                      {!resume.is_primary && (
                        <button
                          type="button"
                          className={small}
                          disabled={primary.isPending}
                          onClick={() => primary.mutate(resume.id)}
                          aria-label={`Make ${resume.name} the primary resume`}
                        >
                          Make primary
                        </button>
                      )}
                      <button
                        type="button"
                        className={small}
                        disabled={remove.isPending}
                        onClick={() => {
                          if (
                            window.confirm(
                              `Delete "${resume.name}" and its profile? The file is removed and this cannot be undone.`,
                            )
                          )
                            remove.mutate(resume.id);
                        }}
                        aria-label={`Delete ${resume.name}`}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error.message}
        </p>
      )}
    </div>
  );
}
