
# Product Requirements Document

## 1. Product Working Name

**RoleRadarAI**

A personal job-discovery, qualification-ranking, and job-application copilot focused initially on companies certified under Denmark's SIRI Fast-track Scheme.

---

# 2. Product Vision

Build a personal job-search application that can:

1. Maintain the official list of SIRI Fast-track certified companies.
2. Make EURES a mandatory discovery step for each target company.
3. Collect relevant vacancies from permitted original employer/ATS sources.
4. Compare each vacancy against the user's resume.
5. Rank opportunities using transparent, repeatable scoring.
6. Track applications.
7. Later generate application materials through specialized LangGraph workflows.

The system should reduce a workflow that currently takes hours:

```text
Find eligible companies
    ↓
Search EURES
    ↓
Look for relevant roles
    ↓
Read each JD
    ↓
Compare JD with resume
    ↓
Decide whether to apply
    ↓
Tailor resume
    ↓
Write outreach
    ↓
Write cover letter
    ↓
Track application
```

into:

```text
SIRI company database
    ↓
EURES discovery queue
    ↓
Relevant vacancy ingestion
    ↓
OpenJev qualification analysis
    ↓
Ranked opportunities
    ↓
User selects a role
    ↓
LangGraph application workflow
    ↓
Application package
```

---

# 3. Primary User

Initially this is a **single-user personal application**.

The user:

- is actively searching for jobs in Europe;
- particularly values companies eligible for Denmark's Fast-track Scheme;
- wants EURES included in the discovery workflow;
- wants to avoid manually checking ~1,000 companies repeatedly;
- wants objective and explainable job/resume matching;
- later wants AI assistance for applications and recruiter outreach.

Multi-user SaaS functionality is explicitly not required for the initial MVP.

---

# 4. Primary Problem

The difficult part of the job search is not merely discovering vacancies.

The user currently needs to answer several questions for every company:

```text
Is this company SIRI certified?

Does the company currently have vacancies?

Is the vacancy visible through EURES?

Is this role actually relevant to my background?

Do I meet the mandatory requirements?

Which requirements are missing?

Should I spend time applying?

How should I tailor my application?
```

Checking these manually across hundreds of companies is inefficient and inconsistent.

RoleRadarAI should become the user's **job-search operating system**.

---

# 5. Product Goals

## 5.1 MVP goals

The MVP must:

- import the existing SIRI company dataset;
- preserve company name and CVR;
- maintain a company search queue;
- provide an EURES search workflow for every company;
- allow discovered vacancies to be imported from their permitted original source;
- upload and store a master resume;
- extract resume text;
- score a vacancy against that resume using OpenJev;
- calculate a deterministic overall matching score;
- explain why a role received that score;
- rank all discovered jobs;
- allow jobs to be saved, ignored, or marked for application;
- persist results across sessions;
- provide a clean Next.js UI.

## 5.2 Post-MVP goals

Later releases should add:

- cover-letter generation;
- tailored resume generation;
- LinkedIn connection messages;
- LinkedIn recruiter messages;
- recruiter emails;
- hiring-manager emails;
- resume summaries;
- tailored resume bullets;
- ATS keyword suggestions;
- interview preparation;
- application tracking;
- recruiter/contact tracking;
- feedback-based ranking improvements.

---

# 6. Explicit Non-Goals for MVP

Do not build the following during the first implementation:

- autonomous job applications;
- automatic LinkedIn messaging;
- automatic email sending;
- auto-submitting job forms;
- browser-control agents;
- fine-tuning OpenJev;
- fine-tuning Laya;
- vector databases at large scale;
- Kubernetes;
- microservices;
- multiple user accounts;
- payments;
- mobile apps;
- enterprise RBAC.

Build a reliable personal tool first.

---

# 7. Source Strategy

## 7.1 SIRI

The initial company universe comes from SIRI's Fast-track certified-company list.

SIRI describes this page as the list of companies certified by the Danish Agency for International Recruitment and Integration to hire foreign labour under the Fast-track Scheme. Certification is attached to the specific company/CVR.

The already-created workbook:

```text
data/siri_certified_companies_eures_queue.xlsx
```

shall be used as the initial seed dataset.

The database becomes the source of truth after import.

Seed facts (verified 2026-10-01): sheet `SIRI Companies` holds 982 rows, 0 duplicate CVRs, 0 duplicate names. Two CVRs are not 8 characters and are preserved exactly as published: `423380281` (Oticon Denmark A/S) and `8485085` (ROCHE DIAGNOSTICS A/S). Sheet `EURES Queue` holds the same 982 companies with status `Pending`, which imports as `NOT_CHECKED`.

### Re-import rules (Decision 2026-10-01)

- Import is idempotent and upserts by CVR string.
- Re-import updates only SIRI-owned fields: `company_name`, `normalized_name`, `siri_certified`, `siri_source_url`, `siri_last_seen_at`.
- Re-import never overwrites user workflow state: `eures_status`, `eures_last_checked_at`, `eures_notes`, `website_url`, `careers_url`, `ats_provider`.
- Handling of companies that disappear from a later SIRI list is undefined; do not deactivate or delete them until decided (see §83).

Required fields:

```text
company_name
normalized_name
cvr
siri_certified
siri_source_url
siri_last_seen_at
eures_search_url
status
created_at
updated_at
```

---

# 8. EURES Requirement

EURES remains a **required discovery surface**.

EURES itself supports searching vacancies using keyword, company, or job title.

However, its current vacancy terms state that users may not use screen scraping or another automated or manual system to extract job-vacancy data for further processing or republication, and API extraction is reserved for recognized EURES partner organisations.

Therefore the application will use the following architecture.

## MVP EURES workflow

```text
Company
   ↓
Generate EURES company-search URL
   ↓
Open EURES search
   ↓
User identifies interesting vacancy
   ↓
Open original employer / ATS vacancy
   ↓
Paste/import original vacancy URL into RoleRadarAI
   ↓
RoleRadarAI extracts permitted source
   ↓
Normalize JD
   ↓
OpenJev comparison
```

EURES therefore remains part of every company-search workflow.

The application should track:

```text
eures_status:
    NOT_CHECKED
    OPENED
    CHECKED_NO_JOBS
    JOB_FOUND
    ERROR

eures_last_checked_at
eures_search_url
eures_notes
```

### EURES status transitions (Decision 2026-10-01)

| User action | Resulting status | `eures_last_checked_at` |
|---|---|---|
| Open EURES search | `OPENED` (only if currently `NOT_CHECKED`; never downgrades a completed status) | unchanged |
| Mark no jobs (no relevant jobs found on EURES) | `CHECKED_NO_JOBS` | set to now |
| Import a vacancy from this company's queue row (P4) | `JOB_FOUND` | set to now |
| Mark error (EURES search failed or unusable) | `ERROR` | set to now |
| Reset | `NOT_CHECKED` | cleared |
| Add / edit note | unchanged | unchanged |

- `CHECKED_NO_JOBS` means "checked; no relevant jobs found", which covers both "no jobs at all" and "only irrelevant jobs". The UI labels it **No relevant jobs**.
- "Mark checked" / "Mark complete" in §23, §24 and §53 are the same action as **Mark no relevant jobs**. A company with an imported job is completed by becoming `JOB_FOUND`.
- "Next unchecked company" means the next company with status `NOT_CHECKED` or `OPENED`, in import (ID) order.
- "Checked" in counters means any status other than `NOT_CHECKED` and `OPENED`.

### EURES search URL (Decision 2026-10-01)

The URL is generated deterministically from the company's official name, using the same template as the seed workbook:

```text
https://europa.eu/eures/portal/jv-se/search?page=1&resultsPerPage=50&orderBy=BEST_MATCH&locationCodes=dk&keywordsEverywhere=<official name, form-encoded>&publicationPeriod=LAST_MONTH&previousPageType=findJob&lang=en
```

Tests assert the generator reproduces the workbook URL for all 982 companies.

---

# 9. Future Authorized EURES Connector

The codebase must define a connector interface now so authorized EURES access can later replace the manual discovery step.

Example interface:

```python
class JobSourceConnector(Protocol):

    async def search_company(
        self,
        company: Company
    ) -> list[ExternalJob]:
        ...

    async def fetch_job(
        self,
        external_id: str
    ) -> ExternalJob:
        ...

    async def normalize_job(
        self,
        external_job: ExternalJob
    ) -> NormalizedJob:
        ...
```

URL import also needs connector selection by URL (§25), so connectors additionally expose (Decision 2026-10-01):

```python
    def can_handle_url(self, url: str) -> bool: ...

    async def fetch_job_by_url(self, url: str) -> ExternalJob: ...
```

Connectors that do not support a capability (for example `search_company` on a URL-only employer-page connector) raise a typed `UnsupportedOperation` error rather than returning empty results.

Implementations:

```text
EuresDiscoveryConnector
EmployerPageConnector
GreenhouseConnector
LeverConnector
AshbyConnector

future:
EuresAuthorizedConnector
```

`EuresDiscoveryConnector` only builds/searches navigation URLs and records human workflow state.

It does not extract EURES vacancy content.

Once authorized API access is obtained:

```text
EuresAuthorizedConnector
```

can replace it without touching matching, resume, UI, database, or LangGraph logic.

---

# 10. Core Technology Stack

## Frontend

```text
Next.js
TypeScript
App Router
React
Tailwind CSS
shadcn/ui or equivalent component primitives
TanStack Query
React Hook Form
Zod
```

Use Next.js **App Router**, which is the current Next.js router designed around newer React capabilities.

Do not implement the frontend in plain HTML/CSS/JS unless Next.js creates an actual blocking issue.

Preferred choice:

**Next.js + TypeScript.**

---

## Backend

```text
Python 3.12+
FastAPI
Pydantic
SQLAlchemy 2
Alembic
httpx
BeautifulSoup / selectolax
PyMuPDF
python-docx
LangGraph
```

FastAPI provides dependency injection that is suitable for database sessions, authentication later, shared services and provider abstractions.

---

## Database

Use:

```text
PostgreSQL
```

rather than SQLite for the main implementation.

Reasons:

- persistent LangGraph state;
- concurrent workers;
- future vector search;
- application history;
- easier production deployment;
- structured JSON fields;
- reliable migrations.

Development may support SQLite for tests, but PostgreSQL should be the expected runtime.

---

## Worker/queue

Use:

```text
Redis
Celery
```

for long-running tasks.

Examples:

```text
company refresh
job URL extraction
bulk job normalization
OpenJev scoring
agent generation jobs
```

FastAPI's built-in background tasks are useful for small tasks, while its documentation recommends a larger queue system such as Celery for heavier work across processes or servers.

---

# 11. AI Architecture

There are two intentionally separate model roles.

## 11.1 Decision model

Use:

```text
OpenJev MLX 4-bit
```

for:

```text
resume ↔ JD matching
requirement satisfaction
skill fit
experience fit
seniority fit
role fit
domain fit
```

The model is designed to take text/JSON plus labels/rules and return typed decisions, probabilities or scores. The MLX 4-bit checkpoint is approximately 15 GB and targets Apple Silicon.

Run it separately, natively on the macOS host with MLX (https://huggingface.co/openjev/openjev-MLX-4bit), on port **4000**:

```text
http://localhost:4000/v1/systemone
```

OpenJev is **never** run in Docker: MLX needs Apple's Metal GPU, and Docker on macOS runs Linux containers in a VM without Metal access. Port 4000 avoids the Next.js dev server on 3000 (Decision 2026-10-01).

The base URL is configuration (`OPENJEV_BASE_URL`):

- API running natively on the host: `http://localhost:4000`
- API running inside Docker Compose: `http://host.docker.internal:4000`

FastAPI talks to this service through a provider class. The OpenJev HTTP call must not go through the SSRF-guarded job fetcher (§67), which correctly blocks localhost.

Important licensing note:

The linked OpenJev MLX 4-bit weights currently use **CC BY-NC 4.0**, so commercial deployment requires revisiting licensing.

---

## 11.2 Generative model

Use a separate provider for:

```text
cover letters
resume rewriting
outreach
emails
interview preparation
```

Do not tightly couple the architecture to one provider.

Create:

```python
class GenerationProvider(Protocol):

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        schema=None
    ):
        ...
```

Possible implementations later:

```text
OpenAIProvider
AnthropicProvider
LocalModelProvider
OllamaProvider
MLXGenerationProvider
```

The product should work before this provider is configured.

---

# 12. Overall System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         NEXT.JS                             │
│                                                             │
│ Dashboard                                                   │
│ Companies                                                   │
│ EURES Queue                                                 │
│ Jobs                                                        │
│ Matches                                                     │
│ Applications                                                │
│ AI Workspace                                                │
│ Settings                                                    │
└─────────────────────────────┬───────────────────────────────┘
                              │ HTTPS / JSON / SSE
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         FASTAPI                             │
│                                                             │
│ REST API                                                    │
│ Auth abstraction                                            │
│ Resume Service                                              │
│ Company Service                                             │
│ Job Service                                                 │
│ Source Connector Service                                    │
│ Match Service                                               │
│ Application Service                                         │
│ LangGraph Service                                           │
└────────────┬─────────────────────────────┬──────────────────┘
             │                             │
             │                             │
             ▼                             ▼
┌──────────────────────────┐    ┌─────────────────────────────┐
│       POSTGRESQL         │    │           REDIS             │
│                          │    │                             │
│ companies                │    │ celery jobs                 │
│ resumes                  │    │ locks                       │
│ jobs                     │    │ transient state             │
│ matches                  │    └─────────────┬───────────────┘
│ applications             │                  │
│ artifacts                │                  ▼
│ graph checkpoints        │        ┌────────────────────────┐
└──────────────────────────┘        │      CELERY WORKER     │
                                    │                        │
                                    │ source connectors      │
                                    │ parsing                │
                                    │ OpenJev analysis       │
                                    │ agent workflows        │
                                    └────────────┬───────────┘
                                                 │
                          ┌──────────────────────┼─────────────┐
                          │                      │             │
                          ▼                      ▼             ▼
                  ┌──────────────┐      ┌──────────────┐ ┌─────────┐
                  │   OPENJEV    │      │ EMPLOYER /   │ │  LLM    │
                  │ MLX SERVER   │      │ ATS SOURCES  │ │Provider │
                  │ localhost    │      │              │ │         │
                  └──────────────┘      └──────────────┘ └─────────┘
```

---

# 13. Repository Structure

Use a monorepo.

```text
RoleRadarAI/
│
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── types/
│   │   └── tests/
│   │
│   └── api/
│       ├── app/
│       │   ├── api/
│       │   │   └── v1/
│       │   ├── core/
│       │   ├── db/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   ├── connectors/
│       │   ├── agents/
│       │   ├── graphs/
│       │   ├── providers/
│       │   ├── workers/
│       │   └── main.py
│       │
│       ├── migrations/
│       └── tests/
│
├── data/
│   └── siri_certified_companies_eures_queue.xlsx
│
├── docker/
├── scripts/
├── docs/
│   ├── PRD.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── SCORING.md
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# 14. Core Database Model

## Company

```text
id UUID PK
company_name TEXT
normalized_name TEXT
cvr TEXT
siri_certified BOOLEAN
siri_source_url TEXT
siri_last_seen_at TIMESTAMP

eures_search_url TEXT
eures_status ENUM
eures_last_checked_at TIMESTAMP
eures_notes TEXT

website_url TEXT
careers_url TEXT
ats_provider TEXT

active BOOLEAN

created_at
updated_at
```

Unique constraints:

```text
UNIQUE(cvr)
```

CVR must remain a string.

Never cast it to an integer.

---

## Resume

```text
id UUID
name
original_filename
file_path
mime_type

raw_text TEXT
text_hash TEXT

is_primary BOOLEAN

created_at
updated_at
```

---

## CandidateProfile

```text
id UUID
resume_id FK

target_roles JSONB
skills JSONB
years_experience NUMERIC
industries JSONB
education JSONB
certifications JSONB
languages JSONB

preferred_locations JSONB
remote_preference
work_authorization JSONB

created_at
updated_at
```

The profile is user-editable.

Never allow an AI extraction to silently become authoritative.

Profile source (Decision 2026-10-01): OpenJev is a decision/scoring model, not an extractor, and no GenerationProvider exists before P9. So in P2 the CandidateProfile is **entered and edited manually** next to the extracted resume text. An AI-assisted extractor may be added later; its output must be shown as a suggestion that the user accepts or edits.

---

# 15. Job Model

```text
id UUID

company_id FK NULLABLE

title TEXT
normalized_title TEXT

description TEXT

location TEXT
country TEXT
city TEXT

employment_type TEXT
workplace_type TEXT

source_type TEXT
source_url TEXT
external_job_id TEXT

apply_url TEXT

published_at TIMESTAMP
expires_at TIMESTAMP

required_skills JSONB
preferred_skills JSONB
experience_requirements JSONB
education_requirements JSONB
language_requirements JSONB

salary_min NUMERIC
salary_max NUMERIC
salary_currency TEXT

raw_payload JSONB

content_hash TEXT
status ENUM

created_at
updated_at
```

Use `content_hash` for deduplication.

### Job ↔ company link (Decision 2026-10-01)

- Import started from an EURES queue row (or a company page) passes that `company_id`; the job links to it and the company becomes `JOB_FOUND`.
- Import started from `/jobs` with no company context: link only on an exact `normalized_name` match with the extracted employer name; otherwise leave `company_id` NULL and let the user pick the company. Never guess a company from a fuzzy match.

## JobSource (Decision 2026-10-01)

§27 needs one canonical Job with several source references, so the model adds:

```text
id UUID
job_id FK
source_type TEXT          -- jsonld | greenhouse | lever | ashby | generic_html | manual
source_url TEXT           -- original URL as submitted
final_url TEXT            -- after validated redirects
external_job_id TEXT
content_hash TEXT
raw_payload JSONB
fetched_at TIMESTAMP
created_at

UNIQUE(source_url)
```

### Re-import of a known URL (Decision 2026-10-01)

- Same URL, same `content_hash`: no change; return the existing job and record `fetched_at`.
- Same URL, different `content_hash`: do **not** silently overwrite. Store a new JobSource snapshot and flag the job `CONTENT_CHANGED` for the user to accept or reject. Existing match scores stay tied to the old content hash.

---

# 16. MatchScore Model

Never store only a single number.

```text
id UUID

job_id
resume_id

model_provider
model_name
model_revision
rubric_version

must_have_fit
skills_fit
experience_fit
role_fit
seniority_fit
domain_fit
education_fit

hard_blocker BOOLEAN

matched_requirements JSONB
missing_requirements JSONB
uncertain_requirements JSONB

overall_score FLOAT

explanation JSONB

input_hash
created_at
```

This allows complete reproducibility.

---

# 17. Matching Philosophy

OpenJev should not answer:

```text
"What percentage chance do I have of getting this job?"
```

That cannot be reliably known.

Instead it answers narrower questions.

Example dimensions:

```text
Must-have requirements
Technical skills
Relevant experience
Role alignment
Seniority alignment
Domain alignment
Education/certification
```

Each receives an ordinal score.

Example:

```text
0 = clear mismatch
1 = weak
2 = partial
3 = strong
4 = excellent
```

---

# 18. Initial Scoring Formula

Version the formula.

Example `rubric_v1`:

```text
Must-have coverage      30%
Skills fit              25%
Experience fit          20%
Role alignment          10%
Seniority alignment      5%
Domain alignment         5%
Education/certification  5%
                       ----
                       100%
```

Then:

```python
overall_score = (
    must_have * 0.30
    + skills * 0.25
    + experience * 0.20
    + role_alignment * 0.10
    + seniority * 0.05
    + domain * 0.05
    + education * 0.05
)
```

Normalize to:

```text
0–100
```

Weights must live in configuration/database, not hard-coded inside prompts.

---

# 19. Hard Requirements

Some conditions should not be hidden inside an average.

Examples:

```text
mandatory language
security clearance
mandatory licence
mandatory professional qualification
explicit years-of-experience threshold
work-location restriction
```

OpenJev classifies:

```text
MET
PARTIAL
NOT_MET
UNKNOWN
```

Then application code determines whether the requirement is:

```text
blocker
warning
informational
```

---

# 20. Match Explanation

Every scored vacancy must show:

```text
Overall score: 84

Strong matches
✓ Python
✓ PyTorch
✓ LLM application development
✓ REST APIs

Partial matches
△ AWS
△ Kubernetes

Missing requirements
✗ Danish B2

Experience
Strong

Role alignment
Excellent

Seniority
Reasonable

Recommendation category
Strong Match
```

Avoid claiming:

```text
84% chance of getting hired
```

Call it:

```text
Match Score: 84/100
```

---

# 21. Match Categories

UI categories:

```text
85–100  Strong Match
70–84   Good Match
55–69   Stretch
0–54    Low Match
```

These boundaries are application configuration, not model truth.

---

# 22. Resume Upload Flow

User visits:

```text
/settings/profile
```

Uploads:

```text
PDF
DOCX
TXT
```

Backend performs:

```text
file validation
    ↓
secure storage
    ↓
text extraction
    ↓
normalization
    ↓
hash generation
    ↓
candidate profile creation
    ↓
user review
```

User must be able to edit:

```text
target roles
skills
years experience
locations
languages
work authorization
preferred industries
```

---

# 23. Company Discovery Workflow

Companies page should contain:

```text
982 companies

Search:
[ Novo Nordisk ]

Filters:
SIRI certified ✓
EURES checked
Has jobs
Has relevant jobs
Not checked
```

Columns:

```text
Company
CVR
SIRI
EURES status
Jobs found
Relevant jobs
Last checked
Actions
```

Actions:

```text
Open EURES
View jobs
Mark checked
Add note
Open careers page
```

### Phase availability (Decision 2026-10-01)

Controls only appear once their data exists; no placeholder controls.

- P1: search; filters SIRI certified, EURES status (incl. Not checked / Checked); columns Company, CVR, SIRI, EURES status, Last checked; action Open EURES.
- P3: Mark checked (= Mark no relevant jobs, §8), Add note.
- P4: Jobs found column, Has jobs filter, View jobs action, Import job URL.
- P2 + relevance filter (§28): Relevant jobs column, Has relevant jobs filter.
- Open careers page: shown only when `careers_url` is set (empty for every seed company).

---

# 24. EURES Queue UI

Route:

```text
/eures
```

Layout:

```text
┌─────────────────────────────────────────────────────────────┐
│ EURES DISCOVERY QUEUE                                      │
│                                                             │
│ 982 companies       134 checked       848 remaining         │
│                                                             │
│ Search company...                                          │
│                                                             │
│ Filters                                                     │
│ [Not checked] [Jobs found] [No jobs] [Errors]              │
├─────────────────────────────────────────────────────────────┤
│ Company         CVR        Status       Last Checked Action  │
│                                                             │
│ Novo Nordisk    ...        Not checked  —            EURES →│
│ LEGO            ...        Jobs found   Today        EURES →│
│ ...                                                         │
└─────────────────────────────────────────────────────────────┘
```

Clicking:

```text
Open EURES
```

opens the pre-generated company-specific EURES search in a new tab.

The row also exposes:

```text
Mark no jobs
Import job URL
Mark complete
Add note
```

"Mark no jobs" and "Mark complete" are one action, **Mark no relevant jobs** (§8). "Import job URL" is added in P4, when the importer exists. The queue also offers **Next unchecked** (§8) so the user can move through companies in order.

---

# 25. Job Import

Primary workflow:

```text
[ Import Vacancy ]

Job URL:
https://company.com/jobs/123

[Import]
```

Backend:

```text
URL validation
      ↓
domain classification
      ↓
connector selection
      ↓
HTTP retrieval
      ↓
JSON-LD detection
      ↓
ATS adapter
      ↓
HTML extraction fallback
      ↓
normalize
      ↓
deduplicate
      ↓
store
      ↓
enqueue match
```

---

# 26. Source Connector Priority

Use this order:

```text
1. Structured ATS API
2. JobPosting JSON-LD
3. Company-specific adapter
4. Generic permitted HTML extraction
5. Manual JD paste
```

### "Permitted" source (Decision 2026-10-01)

A source is permitted for automated retrieval only when all of these hold:

- the fetch is a single request started by the user for one URL (no crawling, no bulk scraping of career sites);
- the URL is the original employer or ATS posting, **never** a EURES vacancy page (EURES domains are rejected by the importer);
- the site's `robots.txt` does not disallow the path for our user agent; a disallow means "use manual JD paste";
- the ATS public job-board API is used only where it is publicly documented for that purpose, and its endpoint is verified against fixtures before use (§54).

Otherwise the user falls back to manual JD paste.

Supported adapters should eventually include:

```text
Greenhouse
Lever
Ashby
Workday
SmartRecruiters
Teamtailor
GenericJobPage
```

Implement only the first few required by discovered companies during MVP.

Do not attempt to support every ATS immediately.

---

# 27. Job Deduplication

Calculate:

```text
normalized company
+
normalized title
+
location
+
content hash
```

If the same vacancy appears through multiple permitted sources, create:

```text
one canonical Job
multiple JobSource references
```

---

# 28. Cheap Relevance Filter

Do not send every vacancy to OpenJev.

Step 1:

```text
Title filter
```

Target-role keywords configured from CandidateProfile.

Example:

```text
AI Engineer
Machine Learning Engineer
Applied AI Engineer
ML Engineer
LLM Engineer
GenAI Engineer
Data Scientist
NLP Engineer
MLOps Engineer
```

Step 2:

optional semantic retrieval.

Step 3:

OpenJev only evaluates jobs passing initial relevance.

---

# 29. OpenJev Integration

Run OpenJev independently from FastAPI.

```text
FastAPI
    |
    | HTTP
    ↓
OpenJev local server
localhost:4000
```

Provider:

```python
class OpenJevDecisionProvider:

    async def evaluate_job(
        self,
        resume_text: str,
        candidate_profile: dict,
        job: Job
    ) -> JobMatchResult:
        ...
```

Use timeout handling.

Add retries only for transport failures.

Cache results using:

```text
resume_hash
+
job_content_hash
+
model_revision
+
rubric_version
```

If hash is unchanged:

```text
do not rescore
```

---

# 30. OpenJev Input

State should contain:

```text
CANDIDATE

Target roles:
...

Skills:
...

Experience:
...

Education:
...

Full resume evidence:
...


VACANCY

Company:
...

Role:
...

Description:
...

Required skills:
...

Required experience:
...
```

Questions should return typed output.

Example logical schema:

```json
{
  "must_have_fit": "MET | PARTIAL | NOT_MET | UNKNOWN",
  "skills_fit": 0,
  "experience_fit": 0,
  "role_fit": 0,
  "seniority_fit": 0,
  "domain_fit": 0,
  "education_fit": 0
}
```

The backend calculates the final score.

OpenJev does not own the weighting formula.

---

# 31. Jobs UI

Route:

```text
/jobs
```

Table:

```text
Role
Company
Location
Source
Published
Match
Status
```

Filters:

```text
Match > 70
Company
Country
Title
Source
SIRI only
Saved
Applied
Not applied
```

Sorting:

```text
Match score
Newest
Company
Title
```

---

# 32. Job Detail Screen

Route:

```text
/jobs/[id]
```

Example:

```text
AI Engineer
Company XYZ

Copenhagen, Denmark

MATCH SCORE
86 / 100

──────────────────────────

Must-have       4/4
Skills          3.7/4
Experience      3.5/4
Role            4/4
Seniority       3/4
Domain          3.5/4

MATCHED

✓ Python
✓ PyTorch
✓ LLM development
✓ REST APIs

PARTIAL

△ AWS
△ Kubernetes

MISSING

✗ Danish language requirement

──────────────────────────

[Open Original Job]
[Save]
[Ignore]
[Apply]
[Generate Application Pack]
```

---

# 33. Dashboard

Route:

```text
/
```

Display:

```text
SIRI companies        982
Companies checked     134
Active jobs           87
Strong matches        14
Applications          8
Interviews            2
```

Sections:

```text
Top matches
Recently discovered
Needs review
Application pipeline
```

---

# 34. Application Tracking

Application states:

```text
DISCOVERED
SAVED
PREPARING
APPLIED
RECRUITER_SCREEN
INTERVIEW
FINAL_INTERVIEW
OFFER
REJECTED
WITHDRAWN
EXPIRED
```

Store:

```text
application_date
job_id
resume_version
cover_letter_version
contact
notes
status
next_action
```

---

# 35. LangGraph Architecture

Do not make everything an agent.

Use deterministic services for:

```text
company imports
HTTP retrieval
parsing
normalization
deduplication
scoring formula
database updates
```

Use LangGraph where stateful AI workflows provide value.

LangGraph's `StateGraph` works around nodes reading/writing shared state, while its checkpointing supports persisted and resumable workflows.

---

# 36. Job Processing Graph

```text
START
   ↓
load_job
   ↓
load_resume
   ↓
validate_inputs
   ↓
extract_job_requirements
   ↓
openjev_evaluation
   ↓
calculate_score
   ↓
persist_match
   ↓
END
```

This graph should be predictable.

No autonomous tool selection is necessary.

---

# 37. Application Generation Graph

Triggered only when user clicks:

```text
Generate Application Pack
```

Graph:

```text
                  START
                    │
                    ▼
              build_context
                    │
       ┌────────────┼─────────────┐
       │            │             │
       ▼            ▼             ▼
resume_tailor   cover_letter    outreach
       │            │             │
       └────────────┼─────────────┘
                    ▼
                 merge
                    │
                    ▼
              fact_checker
                    │
                    ▼
              human_review
                    │
                    ▼
                  END
```

---

# 38. Resume Tailoring Node

Outputs:

```text
tailored professional summary
suggested bullet rewrites
ATS keyword recommendations
missing keyword warnings
```

Rule:

**Never invent experience.**

Every generated claim should map to evidence in the master resume.

---

# 39. Outreach Node

Can generate:

```text
LinkedIn connection note
LinkedIn recruiter DM
recruiter email
hiring-manager email
```

Each receives the same trusted context:

```text
candidate evidence
job description
company
match report
```

---

# 40. Cover Letter Node

Generate:

```text
concise
specific
company-aware
JD-grounded
resume-grounded
```

Avoid generic phrases wherever evidence is available.

---

# 41. Fact Checker Node

Mandatory.

Input:

```text
master resume
candidate profile
job description
all generated artifacts
```

Output:

```text
SUPPORTED
UNSUPPORTED
UNCERTAIN
```

for meaningful factual claims.

Unsupported claims are removed or returned for regeneration.

---

# 42. Human-in-the-Loop

No application document should be sent anywhere automatically.

LangGraph supports persisted human-intervention workflows through checkpointing and interrupts.

Required stage:

```text
AI generates
    ↓
Fact checker
    ↓
USER REVIEW
    ↓
Approve/Edit
    ↓
Export
```

---

# 43. Backend API

Base:

```text
/api/v1
```

## Health

```http
GET /health
GET /health/openjev
GET /health/database
```

---

## Resume

```http
POST   /resumes
GET    /resumes
GET    /resumes/{id}
DELETE /resumes/{id}

POST   /resumes/{id}/set-primary
GET    /resumes/{id}/profile
PATCH  /resumes/{id}/profile
```

---

## Companies

```http
GET    /companies
GET    /companies/{id}

POST   /companies/import/siri
POST   /companies/import/excel

PATCH  /companies/{id}

POST   /companies/{id}/mark-eures-checked
POST   /companies/{id}/mark-no-jobs
```

---

## EURES

```http
GET /companies/{id}/eures-search
```

Response:

```json
{
  "company_id": "...",
  "company_name": "...",
  "url": "...",
  "status": "NOT_CHECKED"
}
```

---

## Jobs

```http
POST /jobs/import-url
POST /jobs/import-text

GET  /jobs
GET  /jobs/{id}

PATCH /jobs/{id}
DELETE /jobs/{id}
```

---

## Matching

```http
POST /jobs/{id}/score

POST /match-runs
GET  /match-runs/{id}

GET /matches
GET /matches/{id}
```

---

## Applications

```http
POST  /applications
GET   /applications
GET   /applications/{id}
PATCH /applications/{id}
```

---

## Agents

Future:

```http
POST /jobs/{id}/application-pack

GET /agent-runs/{id}

POST /agent-runs/{id}/approve
POST /agent-runs/{id}/reject
POST /agent-runs/{id}/resume
```

---

# 44. Progress Updates

Long-running operations should return immediately.

Example:

```http
POST /match-runs
```

returns:

```json
{
  "run_id": "...",
  "status": "QUEUED"
}
```

Frontend receives progress using:

```text
Server-Sent Events
```

Preferred over WebSockets initially because communication is predominantly server → client.

---

# 45. Main Frontend Routes

```text
/
 /settings/profile
 /companies
 /companies/[id]
 /eures
 /jobs
 /jobs/[id]
 /matches
 /applications
 /applications/[id]
 /workspace/[jobId]
 /settings
```

---

# 46. Navigation

Desktop sidebar:

```text
RoleRadarAI

Dashboard
Companies
EURES Queue
Jobs
Matches
Applications

AI Workspace

Settings
```

---

# 47. Visual Design

Style direction:

```text
clean
professional
data-focused
minimal
desktop-first
responsive
```

Avoid:

```text
large decorative gradients
chatbot-first interfaces
excessive cards
animations with no functional value
```

This is a productivity application.

Information density matters.

---

# 48. Design System

Use:

```text
8px spacing system
responsive grids
accessible contrast
consistent score badges
keyboard-friendly tables
loading skeletons
empty states
```

Core components:

```text
Button
Input
Select
Dialog
Drawer
Badge
Table
Tabs
Progress
Tooltip
DropdownMenu
Command/Search
Toast
```

---

# 49. Score Visualization

Use a clear score:

```text
86
Strong Match
```

and dimension bars:

```text
Skills       █████████░ 90
Experience   ████████░░ 82
Role         ██████████ 96
Seniority    ███████░░░ 72
```

Users must be able to inspect the reasoning.

Never make the overall score the only available information.

---

# 50. Phase 0 — Repository Bootstrap

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 51. Phase 1 — SIRI Company Foundation

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 52. Phase 2 — Resume Foundation

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 53. Phase 3 — EURES Discovery Workflow

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 54. Phase 4 — Job Source Connectors

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 55. Phase 5 — OpenJev Integration

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 56. Phase 6 — Ranked Matching Experience

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 57. Phase 7 — Bulk Processing

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 58. Phase 8 — Application Tracking

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 59. Phase 9 — Generative AI Provider

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 60. Phase 10 — LangGraph Application Pack

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 61. Phase 11 — AI Workspace UI

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 62. Phase 12 — Feedback Learning

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 63. Phase 13 — Authorized EURES Integration

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 64. Testing Strategy

## Backend unit tests

Test:

```text
company normalization
CVR preservation
job deduplication
score calculation
hard blockers
resume hashing
job hashing
connector selection
OpenJev response parsing
```

---

## Backend integration tests

Test:

```text
PostgreSQL
Celery
Redis
API endpoints
fixture-based ATS extraction
```

---

## Frontend

Use:

```text
Vitest
React Testing Library
Playwright
```

Critical Playwright flows:

```text
upload resume
browse companies
open EURES queue
import vacancy URL
score vacancy
view result
save vacancy
create application
```

---

# 65. Reliability Rules

Every external operation must support:

```text
timeout
structured errors
retry classification
logging
```

Never allow one failed company to terminate a batch.

Example:

```text
Company A → success
Company B → unsupported source
Company C → timeout
Company D → success
```

The queue continues.

---

# 66. Observability

Log structured events:

```text
company_imported
eures_opened
job_import_started
job_import_completed
job_import_failed
match_started
match_completed
match_failed
agent_started
agent_completed
```

Each event should include:

```text
run_id
company_id
job_id
duration
status
```

Never log the complete resume by default.

---

# 67. Security

The URL importer also rejects EURES hosts (§26), resolves DNS once and connects to the validated IP (no DNS-rebinding window), and re-validates every redirect hop.

Resume and application materials contain private information.

Requirements:

```text
uploads outside public web directory
validated MIME types
filename sanitization
request-size limit
no arbitrary local file paths
no arbitrary shell execution
SSRF protections for URL importer
domain/redirect validation
HTML sanitization
secrets via environment variables
```

The URL importer must explicitly block:

```text
localhost
127.0.0.1
private network ranges
metadata endpoints
file://
ftp://
```

---

# 68. Data Retention

For the personal MVP:

Keep:

```text
resume
companies
jobs
matches
applications
generated artifacts
```

until explicitly deleted.

Provide:

```text
Delete Resume
Delete Job
Delete Generated Artifact
Delete All Personal Data
```

---

# 69. Performance Targets

For normal UI APIs:

```text
p95 < 500 ms
```

excluding AI and source retrieval.

Job import:

```text
target < 10 seconds
```

AI scoring:

asynchronous.

UI must never freeze waiting for OpenJev.

---

# 70. MVP Definition of Done

The first truly useful version is complete when the user can perform this exact flow:

```text
1. Start application.

2. See all 982 SIRI companies.

3. Upload master resume.

4. Open EURES queue.

5. Select a company.

6. Open that company's EURES search.

7. Find a relevant vacancy.

8. Import its permitted original employer/ATS URL.

9. RoleRadarAI extracts the complete JD.

10. OpenJev compares JD against resume.

11. RoleRadarAI calculates a 0–100 Match Score.

12. User sees:
      strengths
      missing requirements
      uncertainties
      dimension scores

13. User saves or ignores vacancy.

14. Ranked Matches page updates.

15. Application can be moved into the application pipeline.
```

Everything after this is enhancement.

---

# 71. Codex Build Instructions

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 72. Coding Conventions

Backend:

```text
async FastAPI routes
Pydantic schemas
SQLAlchemy repositories/services
dependency injection
typed functions
service-level tests
```

Frontend:

```text
TypeScript strict mode
server components by default
client components only where interaction requires them
feature-oriented components
API client abstraction
Zod validation
```

---

# 73. Provider Boundaries

These abstractions must exist from the beginning:

```text
CompanySource
JobSourceConnector
DecisionProvider
GenerationProvider
ResumeParser
EmbeddingProvider
StorageProvider
```

This prevents vendor lock-in.

---

# 74. First Development Milestone

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 75. Second Development Milestone

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 76. Third Development Milestone

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 77. Fourth Development Milestone

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 78. Fifth Development Milestone

Moved to `docs/IMPLEMENTATION_PLAN.md` (same section number).

---

# 79. Future Architecture

Eventually:

```text
                     ┌─────────────┐
                     │    SIRI     │
                     └──────┬──────┘
                            │
                            ▼
                    Company Universe
                            │
          ┌─────────────────┴────────────────┐
          │                                  │
          ▼                                  ▼
        EURES                         Employer Sources
        discovery                     ATS / Career Site
          │                                  │
          └─────────────────┬────────────────┘
                            ▼
                          Jobs
                            │
                            ▼
                    Relevance Filter
                            │
                            ▼
                         OpenJev
                            │
                            ▼
                       Match Ranker
                            │
                            ▼
                         User
                            │
                       selects job
                            │
                            ▼
                        LangGraph
              ┌─────────────┼──────────────┐
              │             │              │
              ▼             ▼              ▼
           Resume        Outreach       Interview
              │             │              │
              └─────────────┼──────────────┘
                            ▼
                      Fact Checker
                            │
                            ▼
                       User Approval
                            │
                            ▼
                       Application
```

---

# 80. Core Product Principle

RoleRadarAI should not behave like:

```text
"AI says this job is 86% suitable."
```

It should behave like:

```text
"This role scored 86/100 under your current rubric.

You strongly satisfy:
- Python
- LLM development
- backend APIs
- relevant experience

You partially satisfy:
- AWS
- Kubernetes

One requirement needs review:
- Danish language requirement

Here is the evidence used for every conclusion."
```

That distinction will make the application significantly more trustworthy and useful.

---

# 81. Final Architecture Decision

For the initial implementation:

```text
Frontend
Next.js + TypeScript

Backend
FastAPI

Database
PostgreSQL

Async jobs
Redis + Celery

Workflow / Agents
LangGraph

Decision model
OpenJev MLX 4-bit

Generation model
Provider abstraction; configure later

Company universe
SIRI

Mandatory job discovery workflow
EURES

Job-content source
Original employer / ATS source where permitted

Deployment
Local-first initially
```

This architecture keeps SIRI and EURES central to the job-search experience while ensuring the rest of RoleRadarAI is modular, testable and capable of evolving into a more automated workflow when authorized EURES access is available.

---

# 82. Decision Log

| Date | Decision | Where |
|---|---|---|
| 2026-10-01 | Product name is **RoleRadarAI** (replaces CareerScout / JobSignal). | all docs |
| 2026-10-01 | OpenJev runs natively on the macOS host (MLX), port **4000**; never in Docker. | §11.1, ARCHITECTURE.md |
| 2026-10-01 | Build order: P0 → P1 → P3 → P4 → P2 → P5 → … (user instruction: working discovery slice before resume and AI). | IMPLEMENTATION_PLAN.md |
| 2026-10-01 | Company re-import upserts by CVR and never overwrites EURES workflow state. | §7.1 |
| 2026-10-01 | EURES status transitions; "Mark checked" = "Mark complete" = "Mark no relevant jobs" → `CHECKED_NO_JOBS`. | §8 |
| 2026-10-01 | EURES URL generated from the workbook's template. | §8 |
| 2026-10-01 | Connector protocol adds `can_handle_url` / `fetch_job_by_url`. | §9 |
| 2026-10-01 | CandidateProfile is manual entry in P2. | §14 |
| 2026-10-01 | `Job.company_id` is nullable; company link rules; `JobSource` model; changed content creates a snapshot rather than an overwrite. | §15 |
| 2026-10-01 | Companies UI shows only controls whose data exists in the current phase. | §23 |
| 2026-10-01 | Definition of a "permitted" source. | §26 |
| 2026-10-01 | Profile route is `/settings/profile` (Profile sits under Settings in the §46 navigation). | §22, §45 |

---

# 83. Open Decisions

These are unresolved. Do not invent answers; resolve with the user before the listed phase starts.

| ID | Question | Blocks | Notes |
|---|---|---|---|
| OD-1 | OpenJev request/response contract for `/v1/systemone` (payload shape, label/rule format, output schema, model revision field). | P5 | Get it from the running server or the model card; do not guess. |
| OD-2 | Numeric value of `must_have_fit` (MET / PARTIAL / NOT_MET / UNKNOWN) inside the 0–4 formula, especially UNKNOWN. | P5 | e.g. MET=4, PARTIAL=2, NOT_MET=0, UNKNOWN=excluded and flagged; needs approval. |
| OD-3 | Effect of a hard blocker on `overall_score` and category: cap the score, force "Low Match", or show a separate blocker badge with the score unchanged. | P5 | §19 requires blockers not to be hidden inside an average. |
| OD-4 | Dimension display format: `x/4` ordinals (§32) or 0–100 bars (§49). Ordinals from the model are integers, so "3.7/4" in §32 has no defined source. | P5/P6 | |
| OD-5 | What happens to companies missing from a later SIRI list (keep, mark `siri_certified=false`, or `active=false`). | future SIRI refresh | Not needed for the one-time seed import. |

