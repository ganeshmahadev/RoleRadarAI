import type { Company, CompanyPage } from "@/lib/api/companies";
import type { Job } from "@/lib/api/jobs";

export function makeCompany(overrides: Partial<Company> = {}): Company {
  return {
    id: "00000000-0000-4000-8000-000000000001",
    company_name: "3Shape A/S",
    normalized_name: "3shape",
    cvr: "25553489",
    source_position: 2,
    siri_certified: true,
    siri_source_url: "https://nyidanmark.dk/pl-PL/Words-and-concepts/SIRI/Certified-companies",
    siri_last_seen_at: "2026-09-30T00:00:00Z",
    eures_search_url:
      "https://europa.eu/eures/portal/jv-se/search?page=1&keywordsEverywhere=3Shape+A%2FS",
    eures_status: "NOT_CHECKED",
    eures_last_checked_at: null,
    eures_notes: null,
    website_url: null,
    careers_url: null,
    ats_provider: null,
    active: true,
    jobs_count: 0,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    ...overrides,
  };
}

export function makePage(
  items: Company[],
  total = items.length,
  page = 1,
  pageSize = 50,
): CompanyPage {
  return { items, total, page, page_size: pageSize };
}

export function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "10000000-0000-4000-8000-000000000001",
    title: "Applied AI Engineer",
    employer_name: "Example Fintech",
    company: {
      id: "00000000-0000-4000-8000-000000000001",
      company_name: "3Shape A/S",
      cvr: "25553489",
    },
    location: "Copenhagen, Denmark",
    source_type: "greenhouse",
    source_url: "https://job-boards.greenhouse.io/examplefintech/jobs/7001001",
    published_at: "2026-09-03T17:30:34Z",
    created_at: "2026-10-01T10:00:00Z",
    source_update_pending: false,
    description: "About the role\n\nBuild LLM-powered tools.",
    country: null,
    city: null,
    employment_type: null,
    workplace_type: null,
    external_job_id: "7001001",
    apply_url: "https://job-boards.greenhouse.io/examplefintech/jobs/7001001",
    expires_at: null,
    content_hash: "abc",
    updated_at: "2026-10-01T10:00:00Z",
    sources: [
      {
        id: "20000000-0000-4000-8000-000000000001",
        source_type: "greenhouse",
        source_url: "https://job-boards.greenhouse.io/examplefintech/jobs/7001001",
        final_url: null,
        status: "ACCEPTED",
        content_hash: "abc",
        fetched_at: "2026-10-01T10:00:00Z",
        normalized: {},
      },
    ],
    ...overrides,
  };
}
