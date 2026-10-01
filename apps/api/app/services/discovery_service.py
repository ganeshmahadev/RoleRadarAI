"""Automated discovery runs (PRD §84, user override for local testing).

scrape job boards (JobSpy) → EURES scan → import (existing pipeline, exact SIRI linking,
cross-board dedup) → score relevant unscored jobs until the time budget.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import timedelta
from typing import Any

from anyio import to_thread
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.discovery.eures_scan import (
    DETAIL_URL,
    PAGE_SIZE,
    EuresBlocked,
    EuresClient,
    EuresError,
    dedupe,
    employer_matches,
    legal_id,
    parse_hits,
    to_job,
)
from app.discovery.jobspy_source import (
    SITES,
    JobSpyClient,
    SearchSpec,
    build_params,
    is_blocked,
    json_safe,
    row_to_job,
)
from app.models import (
    Company,
    DiscoveryPhase,
    DiscoveryRun,
    DiscoverySettings,
    DiscoveryTrigger,
    EuresStatus,
    Job,
    JobSource,
    MatchRun,
    Resume,
    RunScope,
    RunStatus,
)
from app.providers.decision import DecisionProvider
from app.services import job_import, match_run_service, match_service
from app.services.eures_workflow import Clock, utc_now
from app.services.job_import import ImportOutcome

logger = logging.getLogger(__name__)

ACTIVE = (RunStatus.QUEUED, RunStatus.RUNNING)
SIMILAR_WITHIN_DAYS = 30
SETTINGS_ID = 1
Sleep = Callable[[float], Awaitable[None]]
EURES_MAX_PAGES = 4  # per search term (50 results per page)


class DiscoveryDisabled(AppError):
    code = "DISCOVERY_DISABLED"
    http_status = 409


class DiscoveryAlreadyActive(AppError):
    code = "DISCOVERY_ALREADY_ACTIVE"
    http_status = 409


class NoSearchTerms(AppError):
    code = "NO_SEARCH_TERMS"


class DiscoveryRunNotFound(AppError):
    code = "DISCOVERY_RUN_NOT_FOUND"
    http_status = 404


# --- settings ---------------------------------------------------------------------------------


async def get_settings_row(session: AsyncSession) -> DiscoverySettings:
    row = await session.get(DiscoverySettings, SETTINGS_ID)
    if row is None:
        row = DiscoverySettings(id=SETTINGS_ID)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def update_settings(
    session: AsyncSession, row: DiscoverySettings, changes: dict[str, Any]
) -> DiscoverySettings:
    for key, value in changes.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row


async def profile_roles(session: AsyncSession) -> list[str]:
    resume = await session.scalar(select(Resume).where(Resume.is_primary.is_(True)))
    return [r for r in resume.profile.target_roles if r.strip()] if resume else []


async def effective_terms(session: AsyncSession, row: DiscoverySettings) -> list[str]:
    explicit = [t for t in row.search_terms if t.strip()]
    return explicit or await profile_roles(session)


def snapshot(row: DiscoverySettings, terms: list[str]) -> dict[str, Any]:
    return {
        "terms": terms,
        "location": row.location,
        "sites": [s for s in row.sites if s in SITES],
        "results_per_site": row.results_per_site,
        "hours_old": row.hours_old,
        "eures_enabled": row.eures_enabled,
        "eures_companies_per_run": row.eures_companies_per_run,
        "scrape_budget_minutes": row.scrape_budget_minutes,
        "total_budget_minutes": row.total_budget_minutes,
    }


# --- create / cancel --------------------------------------------------------------------------


async def create_run(session: AsyncSession, trigger: DiscoveryTrigger) -> DiscoveryRun:
    config = get_settings()
    row = await get_settings_row(session)
    if not config.discovery_jobspy_enabled and not (
        row.eures_enabled and config.eures_scraper_enabled
    ):
        raise DiscoveryDisabled(
            "Automated discovery is off. Set DISCOVERY_JOBSPY_ENABLED=true in .env "
            "(PRD §84) and restart the API and worker."
        )
    if await session.scalar(select(DiscoveryRun.id).where(DiscoveryRun.status.in_(ACTIVE))):
        raise DiscoveryAlreadyActive("A discovery run is already in progress")
    terms = await effective_terms(session, row)
    if not terms:
        raise NoSearchTerms(
            "Add search terms in Discover settings, or target roles in your profile"
        )
    run = DiscoveryRun(trigger=trigger, status=RunStatus.QUEUED, settings=snapshot(row, terms))
    session.add(run)
    await session.commit()
    logger.info(
        "discovery_run_created", extra={"event": "discovery_run_created", "run_id": str(run.id)}
    )
    return run


async def cancel_run(session: AsyncSession, run: DiscoveryRun) -> DiscoveryRun:
    """Stops after the current search or scored job."""
    if run.status in ACTIVE:
        if run.status is RunStatus.QUEUED:
            run.phase, run.completed_at = DiscoveryPhase.FINISHED, utc_now()
        run.status = RunStatus.CANCELLED
        if run.match_run_id:
            match_run = await session.get(MatchRun, run.match_run_id)
            if match_run is not None:
                await match_run_service.cancel_run(session, match_run)
        await session.commit()
    return run


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> DiscoveryRun:
    run = await session.get(DiscoveryRun, run_id, populate_existing=True)
    if run is None:
        raise DiscoveryRunNotFound("Discovery run not found")
    return run


async def list_runs(session: AsyncSession, *, limit: int) -> list[DiscoveryRun]:
    rows = await session.execute(
        select(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).limit(limit)
    )
    return list(rows.scalars())


# --- execute ----------------------------------------------------------------------------------


async def _cancelled(session: AsyncSession, run: DiscoveryRun) -> bool:
    await session.refresh(run, ["status"])
    return run.status is RunStatus.CANCELLED


def _entry(
    source: str, term: str | None, status: str, message: str | None = None
) -> dict[str, Any]:
    return {
        "source": source,
        "term": term,
        "status": status,
        "message": message,
        "found": 0,
        "created": 0,
        "attached": 0,
        "unchanged": 0,
        "skipped": 0,
        "linked_siri": 0,
    }


async def _store(
    session: AsyncSession,
    run: DiscoveryRun,
    entry: dict[str, Any],
    job: Any,
    raw: dict[str, Any] | None,
    source: str,
    *,
    company_id: uuid.UUID | None = None,
) -> bool:
    """Import one discovered job and count the outcome. Returns True when stored."""
    try:
        result = await job_import.store_normalized(
            session,
            job,
            raw_payload=raw,
            company_id=company_id,
            similar_within_days=SIMILAR_WITHIN_DAYS,
            checked_by="scan",
        )
    except AppError:
        await session.rollback()
        entry["skipped"] += 1
        return False
    if result.outcome is ImportOutcome.CREATED:
        entry["created"] += 1
        run.new_jobs = [
            *run.new_jobs,
            {"id": str(result.job.id), "title": result.job.title, "source": source},
        ]
        if result.job.company_id:
            entry["linked_siri"] += 1
    elif result.outcome is ImportOutcome.ATTACHED_SOURCE:
        entry["attached"] += 1
    else:
        entry["unchanged"] += 1
    return True


async def _import_rows(
    session: AsyncSession,
    run: DiscoveryRun,
    entry: dict[str, Any],
    site: str,
    rows: list[dict[str, Any]],
) -> None:
    entry["found"] = len(rows)
    for raw in rows:
        job = row_to_job(raw, site)
        if job is None:
            entry["skipped"] += 1
            continue
        await _store(session, run, entry, job, json_safe(raw), site)


async def _known_eures_job(session: AsyncSession, job_id: str) -> Job | None:
    """A vacancy already imported from EURES: no detail request needed."""
    return (
        await session.execute(
            select(Job)
            .join(JobSource, JobSource.job_id == Job.id)
            .where(JobSource.source_url == DETAIL_URL.format(id=job_id))
            .limit(1)
        )
    ).scalar_one_or_none()


async def _eures_phase(
    session: AsyncSession,
    run: DiscoveryRun,
    eures: EuresClient,
    sources: list[dict[str, Any]],
    clock: Clock,
) -> None:
    """Term search (descriptions come with the results) + rotating per-company scan
    (CVR-confirmed via the detail call; updates the company's EURES status)."""
    cfg = run.settings
    deadline = run.scrape_deadline
    assert deadline is not None
    since = clock() - timedelta(hours=cfg["hours_old"])

    async def checkpoint(entry: dict[str, Any]) -> None:
        run.sources = [*sources, entry]
        await session.commit()

    # a) Search terms, like the user does on the EURES site.
    for term in cfg["terms"]:
        entry = _entry("eures", term, "ok")
        if clock() >= deadline:
            entry["status"], entry["message"] = "skipped", "Scrape time budget reached"
            sources.append(entry)
            continue
        try:
            hits = []
            for page in range(1, EURES_MAX_PAGES + 1):
                data = await eures.search(term, page=page)
                hits += parse_hits(data)
                if len(data["jvs"]) < PAGE_SIZE or len(hits) >= cfg["results_per_site"]:
                    break
            recent = [h for h in dedupe(hits) if h.created is None or h.created >= since]
            entry["found"] = len(recent)
            for hit in recent[: cfg["results_per_site"]]:
                if clock() >= deadline or await _cancelled(session, run):
                    entry["message"] = "Stopped early (time budget)"
                    break
                if await _known_eures_job(session, hit.id) is not None:
                    entry["unchanged"] += 1
                    continue
                detail = await eures.detail(hit.id)
                cvr = legal_id(detail)
                company_id = (
                    await session.scalar(select(Company.id).where(Company.cvr == cvr))
                    if cvr
                    else None
                )
                job = to_job(hit, detail)
                await _store(session, run, entry, job, detail, "eures", company_id=company_id)
        except EuresBlocked as exc:
            entry["status"], entry["message"] = "blocked", str(exc)
            sources.append(entry)
            return  # stop all EURES requests for this run
        except EuresError as exc:
            entry["status"], entry["message"] = "error", str(exc)
        sources.append(entry)
        await checkpoint(entry)

    # b) Rotate through SIRI companies, least recently checked first.
    limit = cfg["eures_companies_per_run"]
    if limit <= 0:
        return
    entry = _entry("eures companies", None, "ok")
    entry.update({"companies_scanned": 0, "companies_with_jobs": 0, "errors": 0})
    companies = (
        (
            await session.execute(
                select(Company)
                .order_by(
                    Company.eures_last_checked_at.asc().nulls_first(), Company.source_position
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    for company in companies:
        if clock() >= deadline or await _cancelled(session, run):
            entry["message"] = f"Stopped after {entry['companies_scanned']} companies (time budget)"
            break
        try:
            data = await eures.search(company.company_name)
            hits = [
                h for h in dedupe(parse_hits(data)) if employer_matches(h, company.normalized_name)
            ]
            entry["found"] += len(hits)
            stored = 0
            for hit in hits:
                known = await _known_eures_job(session, hit.id)
                if known is not None and known.company_id == company.id:
                    entry["unchanged"] += 1
                    stored += 1
                    continue
                detail = await eures.detail(hit.id)
                cvr = legal_id(detail)
                if cvr and cvr != company.cvr:
                    entry["skipped"] += 1  # same name, different company
                    continue
                job = to_job(hit, detail)
                if await _store(session, run, entry, job, detail, "eures", company_id=company.id):
                    stored += 1
            if stored:
                entry["companies_with_jobs"] += 1
            else:
                if company.eures_status in (
                    EuresStatus.NOT_CHECKED,
                    EuresStatus.OPENED,
                    EuresStatus.CHECKED_NO_JOBS,
                ):
                    company.eures_status = EuresStatus.CHECKED_NO_JOBS
                company.eures_last_checked_at = clock()
                company.eures_checked_by = "scan"
            entry["companies_scanned"] += 1
        except EuresBlocked as exc:
            entry["status"], entry["message"] = "blocked", str(exc)
            break
        except EuresError:
            entry["errors"] += 1
        await checkpoint(entry)
    sources.append(entry)


async def execute_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    client: JobSpyClient | None,
    provider: DecisionProvider,
    eures: EuresClient | None = None,
    delays: Sequence[float],
    pause_seconds: float,
    sleep: Sleep = asyncio.sleep,
    clock: Clock = utc_now,
) -> DiscoveryRun | None:
    run = await session.get(DiscoveryRun, run_id)
    if run is None or run.status is not RunStatus.QUEUED:
        return run
    cfg = run.settings
    started = clock()
    run.status, run.started_at = RunStatus.RUNNING, started
    run.scrape_deadline = started + timedelta(minutes=cfg["scrape_budget_minutes"])
    run.deadline = started + timedelta(minutes=cfg["total_budget_minutes"])
    run.phase = DiscoveryPhase.SCRAPING
    await session.commit()
    log = {"run_id": str(run.id)}
    logger.info("discovery_run_started", extra={"event": "discovery_run_started", **log})

    # 1. Job boards (JobSpy), sequential and throttled.
    sources: list[dict[str, Any]] = []
    blocked: set[str] = set()
    if client is None:
        sources.append(_entry("job boards", None, "disabled", "DISCOVERY_JOBSPY_ENABLED is off"))
    else:
        first = True
        for site in cfg["sites"]:
            for term in cfg["terms"]:
                if await _cancelled(session, run):
                    break
                if site in blocked:
                    sources.append(_entry(site, term, "skipped", "Blocked earlier in this run"))
                    continue
                if clock() >= run.scrape_deadline:
                    sources.append(_entry(site, term, "skipped", "Scrape time budget reached"))
                    continue
                if not first:
                    await sleep(pause_seconds)
                first = False
                entry = _entry(site, term, "ok")
                spec = SearchSpec(
                    site, term, cfg["location"], cfg["results_per_site"], cfg["hours_old"]
                )
                try:
                    rows = await to_thread.run_sync(client.scrape, build_params(spec))
                except Exception as exc:  # JobSpy raises many types; never fail the whole run
                    entry["status"] = "blocked" if is_blocked(exc) else "error"
                    entry["message"] = str(exc)[:240]
                    if entry["status"] == "blocked":
                        blocked.add(site)
                else:
                    await _import_rows(session, run, entry, site, rows)
                sources.append(entry)
                run.sources = list(sources)
                await session.commit()
                logger.info(
                    "discovery_source_finished",
                    extra={
                        "event": "discovery_source_finished",
                        "source": site,
                        "status": entry["status"],
                        **log,
                    },
                )

    # 2. EURES scan (PRD §84; endpoints confirmed by the user, OD-7).
    if cfg["eures_enabled"] and not await _cancelled(session, run):
        run.phase = DiscoveryPhase.EURES
        await session.commit()
        if eures is None:
            sources.append(_entry("eures", None, "disabled", "EURES_SCRAPER_ENABLED is off"))
        else:
            await _eures_phase(session, run, eures, sources, clock)
    run.sources = list(sources)
    await session.commit()

    # 3. Score relevant unscored jobs (new ones and leftovers) until the total budget.
    if not await _cancelled(session, run):
        run.phase = DiscoveryPhase.SCORING
        await session.commit()
        scoring = _entry("scoring", None, "ok")
        try:
            if clock() >= run.deadline:
                raise match_run_service.NothingToScore("No time left in this run's budget")
            plan = await match_run_service.plan_run(session, scope=RunScope.UNSCORED)
            match_run = await match_run_service.create_run(session, plan)
            run.match_run_id = match_run.id
            await session.commit()
            await match_run_service.execute_run(
                session,
                provider,
                match_run.id,
                delays=delays,
                sleep=sleep,
                clock=clock,
                deadline=run.deadline,
            )
            scoring["message"] = f"{len(plan.to_score)} relevant jobs queued for scoring"
        except (
            match_run_service.NothingToScore,
            match_run_service.RunAlreadyActive,
            match_service.NoPrimaryResume,
        ) as exc:
            scoring["status"], scoring["message"] = "skipped", exc.message
        run.sources = [*sources, scoring]

    await session.refresh(run, ["status"])
    if run.status is RunStatus.RUNNING:
        run.status = RunStatus.DONE
    run.phase = DiscoveryPhase.FINISHED
    run.completed_at = clock()
    await session.commit()
    logger.info(
        "discovery_run_finished",
        extra={"event": "discovery_run_finished", "status": run.status.value, **log},
    )
    return run


async def fail_run(session: AsyncSession, run_id: uuid.UUID, code: str, message: str) -> None:
    run = await session.get(DiscoveryRun, run_id)
    if run is not None and run.status in ACTIVE:
        run.status, run.phase = RunStatus.FAILED, DiscoveryPhase.FINISHED
        run.error_code, run.error_message, run.completed_at = code, message, utc_now()
        await session.commit()
