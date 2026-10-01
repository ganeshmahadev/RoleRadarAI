import type { Metadata } from "next";

import { JobDetail } from "@/features/jobs/job-detail";

export const metadata: Metadata = { title: "Job · RoleRadarAI" };

export default async function JobPage(props: PageProps<"/jobs/[id]">) {
  const { id } = await props.params;
  return <JobDetail jobId={id} />;
}
