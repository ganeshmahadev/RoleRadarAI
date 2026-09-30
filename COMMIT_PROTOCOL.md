# Autonomous Agent Commit & Handoff Protocol

> Project: SIRI/EURES Job Search Copilot — **RoleRadarAI**
>
> Purpose: This file is the operating contract for Codex, Claude Code, and any other coding agent working on this repository without continuous human supervision.
>
> The repository must always remain understandable and resumable by a fresh agent with **no prior conversation memory**.

---

## 0. Core rule

**Do not rely on chat memory. Persist important state in the repository.**

At every meaningful checkpoint, the repository itself must explain:

1. what the product is;
2. what phase is active;
3. what has already been completed;
4. what remains;
5. what is blocked;
6. what decisions have been made;
7. what verification has been run;
8. what commit contains the latest known-good state.

A new agent must be able to resume from:

```text
AGENTS.md
BACKLOG.md
docs/PRD.md
docs/IMPLEMENTATION_PLAN.md
docs/ARCHITECTURE.md
git log
git status
```

If any of those files do not yet exist, create the missing tracking/documentation file only when its contents are known from the approved product requirements. Do not invent product behavior to fill gaps.

---

# 1. Source-of-truth order

When documents disagree, use this authority order:

1. Security, privacy, data-integrity, and applicable platform constraints.
2. Explicit instructions from the human in the current task.
3. `docs/PRD.md` — product requirements and scope.
4. `docs/IMPLEMENTATION_PLAN.md` — implementation phases, milestone order, and acceptance criteria.
5. `docs/ARCHITECTURE.md` — approved technical architecture and boundaries.
6. `AGENTS.md` — repository map, commands, coding conventions, and current operating rules.
7. `BACKLOG.md` — current execution state and remaining tasks.
8. Existing tested behavior and established repository patterns.
9. Library/framework defaults.

Never let a framework default silently override the PRD or architecture.

If a lower-priority source conflicts with a higher-priority source:

- follow the higher-priority source;
- record the discrepancy in `BACKLOG.md`;
- do not silently "fix" the higher-priority document.

---

# 2. Required repository memory files

## 2.1 `AGENTS.md`

`AGENTS.md` is the **repository map**, not a diary and not the entire PRD.

Keep it short and current.

It should contain:

- product summary;
- source-of-truth documents;
- approved stack;
- repository structure;
- commands for install/dev/test/lint/typecheck/build/migrations;
- architecture boundaries;
- coding conventions;
- safety/security rules;
- commit protocol reference;
- instructions to read `BACKLOG.md` before beginning work.

Update `AGENTS.md` when any of these change:

- stack;
- repository layout;
- canonical commands;
- important architecture boundaries;
- test strategy;
- permanent engineering conventions;
- source-of-truth locations.

Do **not** add transient task progress to `AGENTS.md`.

Transient progress belongs in `BACKLOG.md`.

---

## 2.2 `BACKLOG.md`

`BACKLOG.md` is mandatory persistent project state.

It must be updated:

- before starting a new backlog item;
- whenever an item becomes blocked;
- after finishing an item;
- before every commit that materially advances the project;
- before ending a session;
- before switching to another phase;
- before handing work to another agent.

Every actionable backlog item must have:

```text
ID
Phase
Status
Priority
Goal
Dependencies
Acceptance criteria
Files/areas involved
Verification required
Notes/blockers
Commit hash when completed
```

Allowed statuses:

```text
TODO
IN_PROGRESS
BLOCKED
VERIFYING
DONE
DEFERRED
```

Only **one implementation item per agent/worktree should be `IN_PROGRESS` at a time** unless the tasks are intentionally independent.

Never delete completed history immediately. Move completed items to the completed section so the next agent can understand what happened.

---

# 3. Session start protocol

Every new agent session must do this **before editing code**.

## Step 1 — establish repository state

Run:

```bash
pwd
git status --short --branch
git log --oneline -12
```

If the repository contains uncommitted work:

1. inspect it;
2. identify whether it belongs to the current backlog item;
3. preserve it;
4. do not reset, discard, overwrite, or stash it blindly.

Never assume an uncommitted change is disposable.

---

## Step 2 — read persistent memory

Read, in this order:

```text
AGENTS.md
BACKLOG.md
docs/PRD.md
docs/IMPLEMENTATION_PLAN.md
docs/ARCHITECTURE.md
```

Then read only the detailed docs needed for the active phase.

Do not work from remembered summaries when the repository contains a source document.

---

## Step 3 — inspect the current implementation

Inspect:

- workspace/package manifests;
- existing applications;
- database models and migrations;
- shared components;
- API conventions;
- provider interfaces;
- tests;
- recent commits touching the target area.

Before adding a dependency, search the repository for an existing library or utility that already solves the need.

Before creating a component/service/provider, search for an existing abstraction.

---

## Step 4 — choose exactly one backlog item

Priority order:

1. resume an `IN_PROGRESS` item;
2. unblock a `BLOCKED` item if its dependency is now resolved;
3. take the highest-priority unblocked item in the active phase;
4. only move to the next phase when current-phase exit criteria are satisfied.

Do not cherry-pick exciting future work while foundational tasks remain unfinished.

Set the selected item to:

```text
Status: IN_PROGRESS
```

and add a short start note before editing.

---

# 4. Autonomous overnight behavior

The human may be unavailable.

The absence of a reply is **not permission to guess**.

When a decision is unclear:

### Continue without asking when

- the PRD already defines the behavior;
- existing repository conventions clearly answer it;
- the decision is implementation-local and reversible;
- the choice does not expand product scope;
- the choice does not create a security/privacy/data-integrity risk.

### Do not guess when

- product behavior is undefined;
- the choice changes architecture materially;
- the action is destructive;
- a schema change would destroy or reinterpret stored data;
- credentials/secrets are required;
- an external production action is required;
- a legal/compliance/platform restriction would be bypassed;
- a new integration requires undocumented assumptions.

When blocked:

1. mark the backlog item `BLOCKED`;
2. write the exact blocker;
3. write what information would resolve it;
4. preserve the clean extension point;
5. move to the next independent unblocked backlog item.

Do not stop the entire overnight run because one non-critical item is blocked.

---

# 5. Retry and failure discipline

Do not loop indefinitely.

For the same failure:

```text
attempt 1 → diagnose
attempt 2 → change hypothesis
attempt 3 → final bounded attempt
```

If the third meaningful attempt fails:

- stop repeating the same approach;
- record the failure in `BACKLOG.md`;
- include the exact command/error summary;
- mark the item `BLOCKED` if it cannot proceed;
- move to another safe task.

Never hide failing tests by disabling, skipping, deleting, or weakening them unless the approved requirement explicitly changed and the test is updated to reflect that requirement.

---

# 6. Project architecture contract

The initial approved stack is:

```text
Frontend:
Next.js + TypeScript + App Router

Backend:
Python + FastAPI

Database:
PostgreSQL

Async work:
Redis + Celery

Workflow orchestration:
LangGraph, only where stateful AI workflows add value

Decision model:
OpenJev MLX 4-bit behind a DecisionProvider abstraction

Generation model:
Separate GenerationProvider abstraction

Company source:
SIRI Fast-track certified-company dataset

Mandatory discovery workflow:
EURES

Vacancy content ingestion:
Original employer / ATS source where permitted by the approved integration contract
```

Do not replace these choices casually.

---

# 7. Architecture boundaries that must remain true

## 7.1 Frontend boundary

The browser calls the FastAPI backend.

Do not place:

- model credentials;
- provider secrets;
- privileged source credentials;
- database credentials;
- local filesystem paths;

in frontend code.

---

## 7.2 Job-source boundary

All vacancy sources implement a common connector contract.

Conceptually:

```python
class JobSourceConnector:
    async def search_company(...): ...
    async def fetch_job(...): ...
    async def normalize_job(...): ...
```

Expected implementations may include:

```text
EuresDiscoveryConnector
GreenhouseConnector
LeverConnector
AshbyConnector
GenericJobPageConnector
```

Do not put source-specific parsing throughout business services.

---

## 7.3 AI boundary

Decision logic and generation logic are separate.

```text
DecisionProvider
    -> OpenJevProvider
    -> future LayaProvider / other provider

GenerationProvider
    -> cloud/local generative LLM
```

Do not use the generation model as the authoritative deterministic scorer.

Do not hardcode OpenJev HTTP calls throughout unrelated services.

---

## 7.4 Scoring boundary

The model produces dimension-level evaluations.

Application code owns the final weighted formula.

Never present a job-match score as probability of getting hired.

Use language such as:

```text
Match Score: 84 / 100
```

not:

```text
84% chance of getting the job
```

Persist:

- model ID;
- model revision;
- rubric version;
- resume hash;
- job-content hash;
- dimension outputs;
- final calculated score.

---

## 7.5 LangGraph boundary

Do not make every service an agent.

Use deterministic application code for:

- imports;
- parsing;
- normalization;
- database persistence;
- deduplication;
- hashing;
- scoring formulas;
- permissions;
- validation.

Use LangGraph for stateful multi-step AI workflows such as:

- resume tailoring;
- cover-letter generation;
- outreach generation;
- interview preparation;
- fact checking;
- human approval.

---

# 8. Data-integrity rules

## CVR

CVR must remain a string.

Never coerce CVR to integer merely because most values look numeric.

Preserve source values exactly.

---

## Resume

The original resume is the candidate evidence source of truth.

AI-extracted structured data must remain reviewable/editable.

Generated application material must not invent:

- jobs;
- employers;
- degrees;
- dates;
- responsibilities;
- metrics;
- skills;
- certifications;
- leadership scope.

---

## Job descriptions

Keep:

- original URL;
- source type;
- extracted raw/normalized content;
- content hash;
- import timestamp.

Do not silently overwrite a stored job description when source content changes.

Version or update it deliberately.

---

# 9. Security baseline

All URL ingestion must defend against SSRF.

Block at minimum:

```text
localhost
127.0.0.0/8
::1
private RFC1918 networks
link-local addresses
cloud metadata endpoints
file://
ftp://
```

Validate redirects.

Validate upload MIME types.

Sanitize filenames.

Keep uploads outside public frontend directories.

Never log:

- complete resume text by default;
- API keys;
- tokens;
- secrets;
- private model credentials.

Never commit `.env` files containing secrets.

---

# 10. Implementation workflow for every backlog item

Use this loop:

```text
READ
  ↓
INSPECT
  ↓
PLAN THE SMALLEST COMPLETE SLICE
  ↓
IMPLEMENT
  ↓
TEST
  ↓
REVIEW DIFF
  ↓
UPDATE BACKLOG / AGENTS IF NEEDED
  ↓
COMMIT
  ↓
VERIFY CLEAN STATE
  ↓
CONTINUE
```

Do not code several phases and then create one giant commit.

---

# 11. Before writing code

For the active item, write or confirm:

```text
Goal:
Acceptance criteria:
Existing code to reuse:
Files likely to change:
Schema/API impact:
Tests required:
Known risks:
```

This can live in the corresponding `BACKLOG.md` item.

For a complex task, create a dedicated execution plan under:

```text
docs/exec-plans/active/<BACKLOG_ID>-<slug>.md
```

Move it to:

```text
docs/exec-plans/completed/
```

when the item is done.

---

# 12. Dependency rule

Before installing a dependency:

1. search existing manifests;
2. search existing utilities;
3. confirm the standard library/framework cannot reasonably do it;
4. confirm the dependency fits the approved stack;
5. add the smallest necessary dependency;
6. record meaningful permanent dependency decisions in `AGENTS.md`.

Do not install competing libraries for the same purpose.

Examples:

```text
Do not install Axios if the project standardized on fetch/httpx.
Do not install a second schema library if Zod/Pydantic already owns validation.
Do not install a second UI component framework without explicit approval.
```

---

# 13. Database-change protocol

For every schema change:

1. modify canonical ORM model;
2. create migration;
3. inspect generated migration;
4. ensure migration is non-destructive unless explicitly intended;
5. add/update constraints and indexes;
6. test migration on a development database;
7. update architecture/schema docs if the change is structural;
8. include migration in the same atomic commit as the code that requires it.

Never edit production data manually as a substitute for a migration.

---

# 14. API-change protocol

For each API change:

- define request/response schema;
- validate inputs;
- keep errors structured;
- add tests;
- update generated/manual API documentation where applicable;
- update frontend client types/calls in the same feature slice if required.

Avoid hidden API contracts implemented only by frontend assumptions.

---

# 15. UI implementation rules

Frontend:

```text
Next.js
TypeScript strict mode
App Router
server components by default
client components only when interaction/browser APIs require them
```

Every screen must define:

- loading;
- empty;
- success;
- error;
- disabled/unavailable where applicable.

Every meaningful control must support keyboard operation.

Do not ship placeholder buttons that do nothing.

Do not use `href="#"`.

Do not create a dashboard full of generic cards merely because it is easy.

Prefer task-native UI:

```text
Companies -> searchable/filterable company table
EURES -> persistent discovery queue
Jobs -> dense ranked list/table
Job detail -> evidence + dimension breakdown
Applications -> pipeline/state tracking
AI workspace -> artifact editor/review
```

---

# 16. Testing expectation

A task is not done because the happy path runs once.

Run tests appropriate to the touched area.

## Frontend

Expected categories:

```text
lint
typecheck
unit/component tests
build
Playwright for critical flows
accessibility checks for changed interactive UI
```

## Backend

Expected categories:

```text
ruff/lint
type checking when configured
pytest
database integration tests when schema/repository logic changes
connector fixture tests when parsers change
```

## Connector tests

Do not make a live external careers website the only test fixture.

Store sanitized deterministic HTML/JSON fixtures.

---

# 17. Mandatory pre-commit checklist

Before **every commit**, perform all applicable checks.

## 17.1 Inspect state

```bash
git status --short
git diff --check
git diff
```

If staged files already exist from a prior agent, inspect them before changing the staging area.

---

## 17.2 Search for accidental secrets

At minimum inspect changed files for:

```text
API keys
access tokens
private keys
passwords
.env contents
personal resume data accidentally added to fixtures
```

Do not commit real personal resume contents as a test fixture unless explicitly intended by the human.

Use anonymized fixtures.

---

## 17.3 Run validation

Run the repository's canonical commands from `AGENTS.md`.

Typical target:

```bash
# frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build

# backend
ruff check .
pytest
```

Use the actual repository commands, not these examples blindly.

When a full suite is prohibitively expensive:

1. run the targeted suite;
2. run the highest-value broader validation available;
3. record exactly what was and was not run.

Never write "tests pass" without having run them.

---

## 17.4 Update persistent memory

Before committing:

### Always update `BACKLOG.md`

Record:

- current item status;
- what changed;
- validation performed;
- remaining work;
- blocker if any.

### Update `AGENTS.md` only if permanent repository knowledge changed

Examples:

- a new canonical command;
- repository layout change;
- new provider abstraction;
- new architectural rule;
- new required environment variable;
- new standard library/tool.

Do not churn `AGENTS.md` for every small commit.

---

## 17.5 Review the diff as a reviewer

Ask:

```text
Does this commit do one coherent thing?
Did scope expand?
Did I accidentally modify unrelated files?
Did I duplicate an abstraction?
Did I add a dependency unnecessarily?
Did I weaken security or validation?
Did I leave TODOs that belong in BACKLOG.md?
Did I update tests?
Did I update migrations/docs when required?
Can the next agent understand why this exists?
```

Fix problems before committing.

---

# 18. Commit policy

## 18.1 Commit size

Prefer atomic commits.

One commit should normally represent:

```text
one backlog item
```

or one independently verifiable slice of a larger item.

Avoid:

```text
"build everything"
"misc changes"
"fix stuff"
```

---

## 18.2 Commit message format

Use Conventional Commit style plus the backlog ID.

Format:

```text
<type>(<scope>): <imperative summary> [<BACKLOG_ID>]
```

Examples:

```text
chore(repo): bootstrap web and API workspaces [P0-001]
feat(companies): import SIRI company seed workbook [P1-002]
feat(resume): add PDF resume upload and extraction [P2-003]
feat(eures): add persistent company discovery queue [P3-002]
feat(jobs): add JSON-LD vacancy importer [P4-004]
feat(matches): integrate OpenJev decision provider [P5-003]
fix(connectors): reject private-network URL redirects [P4-007]
test(matches): cover rubric cache invalidation [P5-006]
docs(agents): document canonical migration commands [META-002]
```

Allowed common types:

```text
feat
fix
refactor
test
docs
chore
perf
build
ci
```

---

## 18.3 Commit body

For non-trivial commits, use:

```text
Why:
- reason for the change

What:
- major implementation points

Validation:
- exact commands run

Backlog:
- ID and resulting status
```

Do not paste huge implementation diaries into commit messages.

`BACKLOG.md` owns execution history.

---

# 19. Context-loss checkpoint commits

If the agent is approaching a context/session/tool limit and the active task is not finished:

1. get the work into the safest coherent state possible;
2. run targeted validation for the touched slice;
3. update `BACKLOG.md` with exact remaining work;
4. commit only if the partial state is useful and does not knowingly break the branch.

Use:

```text
chore(checkpoint): preserve <area> progress [<BACKLOG_ID>]
```

The commit body must say:

```text
Incomplete:
- ...

Validated:
- ...

Next:
- exact first next action
```

Do **not** create checkpoint commits that intentionally leave the repository uncompilable if that can reasonably be avoided.

---

# 20. After-commit protocol

Immediately after every commit:

```bash
git status --short --branch
git log -1 --oneline
```

Then update the corresponding completed backlog entry with the commit hash.

If updating `BACKLOG.md` to add the commit hash makes the worktree dirty, include that update in the next documentation checkpoint or use a follow-up documentation commit when necessary.

Preferred pattern for a completed feature:

```text
implementation + tests + BACKLOG status
    ↓
commit
    ↓
record hash in BACKLOG
    ↓
small docs commit only if needed
```

Do not amend published/shared commits unless explicitly instructed.

---

# 21. Pushing/deployment rule

Local commits are allowed as part of autonomous work when the human requested autonomous implementation.

Do not automatically:

- force push;
- rewrite remote history;
- delete remote branches;
- deploy to production;
- publish packages;
- send emails/messages;
- submit job applications;
- trigger paid external operations;

unless the human explicitly authorized that action.

If remote push is part of the human's explicit instruction, use normal non-force push only.

---

# 22. Backlog completion rule

An item may be marked `DONE` only when:

- acceptance criteria are satisfied;
- relevant tests pass;
- lint/typecheck/build pass where applicable;
- migrations are included and verified when required;
- docs are updated when required;
- no known critical regression remains;
- work is committed;
- the commit is identifiable from the backlog.

If verification cannot be performed, use:

```text
VERIFYING
```

or:

```text
BLOCKED
```

—not `DONE`.

---

# 23. Phase-completion rule

A phase may be marked complete only after:

1. every required phase item is `DONE` or explicitly `DEFERRED` with a reason;
2. phase-level acceptance criteria pass;
3. full relevant test suite passes;
4. documentation reflects the final state;
5. the next phase has no hidden dependency on unfinished phase work.

Do not start AI-agent features before the deterministic data pipeline is usable.

---

# 24. Overnight handoff protocol

Before ending an autonomous run for any reason, update `BACKLOG.md` with:

```text
## Overnight handoff

Last updated:
Last commit:
Current branch:
Worktree:
Active phase:
Active item:
Status:

Completed this run:
- ...

Validation:
- ...

Blocked:
- ...

Uncommitted files:
- ...

Exact next action:
1. ...

Useful commands:
- ...

Important observations:
- ...
```

If there is uncommitted work, state exactly why.

The goal is:

> A new Codex/Claude instance should be able to continue in minutes without asking "what was happening?"

---

# 25. `AGENTS.md` maintenance checklist

Whenever permanent project conventions change, review:

```text
Does AGENTS.md still list the correct stack?
Does it point to the correct PRD/plan/architecture files?
Are commands current?
Are ports current?
Are app/package paths current?
Are provider boundaries current?
Are migration/test commands current?
Does it still tell the agent to read BACKLOG.md first?
```

Keep it concise.

If an explanation grows large, move the detail into `docs/` and link to it from `AGENTS.md`.

---

# 26. `BACKLOG.md` maintenance checklist

Every backlog update should preserve:

```text
What is being done?
Why?
What does "done" mean?
What depends on it?
What was verified?
What failed?
What remains?
Which commit contains it?
```

Never write vague entries such as:

```text
fix backend
work on UI
finish AI
clean things
```

Use executable items.

---

# 27. Recommended phase order for this project

```text
P0 Repository bootstrap
P1 SIRI company foundation
P2 Resume foundation
P3 EURES discovery workflow
P4 Job-source connectors
P5 OpenJev matching
P6 Ranked matching UI
P7 Background/bulk processing
P8 Application tracking
P9 Generative model provider
P10 LangGraph application pack
P11 AI workspace
P12 Feedback/evaluation dataset
P13 Authorized EURES connector when available
```

Do not skip the dependency chain without an explicit reason recorded in `BACKLOG.md`.

**Active order (human decision 2026-10-01):** P0 → P1 → P3 → P4 → P2 → P5 → P6 … See `docs/IMPLEMENTATION_PLAN.md`.

---

# 28. Product-specific "do not invent" list

Do not invent:

- visa eligibility for a specific job;
- sponsorship guarantees;
- company willingness to sponsor a particular vacancy;
- hiring probability;
- missing resume experience;
- job requirements absent from the source;
- company relationships/subsidiaries without evidence;
- salaries absent from the vacancy;
- candidate credentials;
- EURES authorization/API access that has not been granted;
- ATS endpoints that have not been verified;
- source permissions that have not been established.

Represent unknown as unknown.

---

# 29. Completion report format

At the end of each autonomous run, produce a concise report:

```text
Completed:
- [ID] item — commit <hash>

Validation:
- command — PASS
- command — PASS

Blocked:
- [ID] blocker

Backlog:
- next item: <ID>

Worktree:
- clean / dirty (explain)

Important notes:
- ...
```

Never claim work was committed, tested, pushed, or deployed without verifying it.

---

# 30. Final operating principle

Optimize for **continuity, correctness, and recoverability**, not the number of files changed.

The repository is the memory.

`AGENTS.md` explains how to work here.

`BACKLOG.md` explains where the work currently stands.

The PRD explains what must be built.

The implementation plan explains in what order.

Git explains exactly what changed.

Keep all five synchronized enough that another agent can safely take over at any time.
