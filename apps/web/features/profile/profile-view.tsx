"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { buttonClass } from "@/components/ui/styles";
import { listResumes } from "@/lib/api/resumes";

import { ProfileForm } from "./profile-form";
import { ResumeList } from "./resume-list";
import { ResumeText } from "./resume-text";
import { ResumeUpload } from "./resume-upload";

export function ProfileView() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ["resumes"],
    queryFn: listResumes,
  });

  const select = (id: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("resume", id);
    router.replace(`${pathname}?${params}`, { scroll: false });
  };

  const requested = searchParams.get("resume");
  const selected =
    data?.find((r) => r.id === requested) ?? data?.find((r) => r.is_primary) ?? data?.[0] ?? null;

  return (
    <div className="space-y-6">
      <section aria-labelledby="resumes-title" className="space-y-3">
        <h2 id="resumes-title" className="text-sm font-semibold">
          Resumes
        </h2>
        <ResumeUpload onUploaded={(resume) => select(resume.id)} />
        {isPending && (
          <div className="h-24 animate-pulse rounded border border-border bg-surface" />
        )}
        {isError && (
          <div role="alert" className="rounded border border-danger/40 p-4 text-sm">
            <p className="font-medium text-danger">Could not load resumes.</p>
            <p className="mt-1 text-muted">{error.message}</p>
            <button type="button" className={`${buttonClass} mt-3`} onClick={() => void refetch()}>
              Retry
            </button>
          </div>
        )}
        {data && data.length === 0 && (
          <p className="rounded border border-dashed border-border px-3 py-6 text-center text-sm text-muted">
            No resume yet. Upload your master resume to start; the first one becomes your primary
            resume.
          </p>
        )}
        {data && data.length > 0 && (
          <>
            <ResumeList resumes={data} selectedId={selected?.id ?? null} onSelect={select} />
            <p className="text-xs text-muted">
              The primary resume is the one used for matching. Each resume has its own profile.
            </p>
          </>
        )}
      </section>

      {selected && (
        <div className="grid gap-6 lg:grid-cols-2">
          <ResumeText key={`text-${selected.id}`} resumeId={selected.id} />
          <ProfileForm
            key={`profile-${selected.id}`}
            resumeId={selected.id}
            resumeName={selected.name}
          />
        </div>
      )}
    </div>
  );
}
