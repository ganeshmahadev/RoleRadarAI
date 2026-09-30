from datetime import UTC, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.commands.import_siri import run
from app.models import Company, EuresStatus
from app.services.siri_import import (
    SiriCompanyRow,
    SiriImportError,
    import_siri_companies,
    read_siri_workbook,
)

SEED = Path(__file__).resolve().parents[3] / "data" / "siri_certified_companies_eures_queue.xlsx"
HEADER = [
    "ID",
    "Company Name (Official)",
    "CVR No.",
    "Search Name",
    "Normalized Name",
    "SIRI Certified",
    "Source Last Updated",
    "Source URL",
]
SOURCE = "https://nyidanmark.dk/pl-PL/Words-and-concepts/SIRI/Certified-companies"


def write_workbook(path: Path, rows: list[list[object]], header: list[str] = HEADER) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "SIRI Companies"
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    workbook.save(path)
    return path


def row(position: int, name: str, cvr: object, certified: str = "Yes") -> list[object]:
    return [position, name, cvr, name, "", certified, datetime(2026, 9, 30), SOURCE]


# --- workbook parsing -------------------------------------------------------------------


def test_reads_full_seed_workbook() -> None:
    rows = read_siri_workbook(SEED)
    assert len(rows) == 982
    assert len({r.cvr for r in rows}) == 982
    by_cvr = {r.cvr: r for r in rows}
    assert by_cvr["423380281"].company_name == "Oticon Denmark A/S"
    assert by_cvr["8485085"].company_name == "ROCHE DIAGNOSTICS A/S"
    assert rows[0] == SiriCompanyRow(
        position=1,
        company_name="&TRADITION A/S",
        cvr="18169304",
        siri_certified=True,
        siri_last_seen_at=datetime(2026, 9, 30, tzinfo=UTC),
        siri_source_url=SOURCE,
    )


def test_rejects_numeric_cvr_cells(tmp_path: Path) -> None:
    path = write_workbook(tmp_path / "w.xlsx", [row(1, "Numeric A/S", 1234567)])
    with pytest.raises(SiriImportError, match="CVR must be a non-empty text cell"):
        read_siri_workbook(path)


def test_rejects_duplicate_cvrs(tmp_path: Path) -> None:
    path = write_workbook(
        tmp_path / "w.xlsx", [row(1, "A A/S", "11111111"), row(2, "B", "11111111")]
    )
    with pytest.raises(SiriImportError, match="duplicate CVR '11111111'"):
        read_siri_workbook(path)


def test_rejects_missing_columns(tmp_path: Path) -> None:
    path = write_workbook(tmp_path / "w.xlsx", [], header=HEADER[:2])
    with pytest.raises(SiriImportError, match="missing column 'CVR No.'"):
        read_siri_workbook(path)


def test_rejects_unknown_certified_value(tmp_path: Path) -> None:
    path = write_workbook(tmp_path / "w.xlsx", [row(1, "A A/S", "11111111", certified="Maybe")])
    with pytest.raises(SiriImportError, match="SIRI Certified must be Yes/No"):
        read_siri_workbook(path)


def test_preserves_unusual_cvr_text(tmp_path: Path) -> None:
    path = write_workbook(
        tmp_path / "w.xlsx",
        [row(1, "Zero A/S", "00012345"), row(2, "Short A/S", "8485085"), row(3, "L", "423380281")],
    )
    assert [r.cvr for r in read_siri_workbook(path)] == ["00012345", "8485085", "423380281"]


# --- persistence ------------------------------------------------------------------------


async def test_imports_full_seed_workbook(session: AsyncSession) -> None:
    rows = read_siri_workbook(SEED)
    result = await import_siri_companies(session, rows)
    assert (result.total, result.created, result.updated, result.unchanged) == (982, 982, 0, 0)

    assert await session.scalar(select(func.count()).select_from(Company)) == 982
    assert await session.scalar(select(func.count(func.distinct(Company.cvr)))) == 982
    stored = {c.cvr: c for c in (await session.execute(select(Company))).scalars()}
    assert {cvr: c.company_name for cvr, c in stored.items()} == {
        r.cvr: r.company_name for r in rows
    }
    assert all(c.eures_search_url.startswith("https://europa.eu/eures/") for c in stored.values())
    assert all(c.eures_status is EuresStatus.NOT_CHECKED for c in stored.values())
    assert stored["8485085"].company_name == "ROCHE DIAGNOSTICS A/S"
    assert stored["18169304"].normalized_name == "&tradition"
    assert stored["18169304"].source_position == 1


async def test_reimport_is_idempotent_and_keeps_eures_state(session: AsyncSession) -> None:
    rows = read_siri_workbook(SEED)
    await import_siri_companies(session, rows)
    company = await session.scalar(select(Company).where(Company.cvr == "25553489"))
    assert company is not None
    checked_at = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    company.eures_status = EuresStatus.CHECKED_NO_JOBS
    company.eures_last_checked_at = checked_at
    company.eures_notes = "Only sales roles"
    company.careers_url = "https://www.3shape.com/careers"
    await session.commit()

    result = await import_siri_companies(session, rows)

    assert (result.created, result.updated, result.unchanged) == (0, 0, 982)
    assert await session.scalar(select(func.count()).select_from(Company)) == 982
    await session.refresh(company)
    assert company.eures_status is EuresStatus.CHECKED_NO_JOBS
    assert company.eures_last_checked_at == checked_at
    assert company.eures_notes == "Only sales roles"
    assert company.careers_url == "https://www.3shape.com/careers"


async def test_reimport_updates_siri_fields_only(session: AsyncSession) -> None:
    original = SiriCompanyRow(1, "Old Name A/S", "12345678", True, None, SOURCE)
    await import_siri_companies(session, [original])
    company = await session.scalar(select(Company))
    assert company is not None
    company.eures_status = EuresStatus.OPENED
    await session.commit()

    renamed = SiriCompanyRow(1, "New Name A/S", "12345678", True, None, SOURCE)
    result = await import_siri_companies(session, [renamed])

    assert result.updated == 1
    await session.refresh(company)
    assert company.company_name == "New Name A/S"
    assert company.normalized_name == "new name"
    assert "keywordsEverywhere=New+Name+A%2FS" in company.eures_search_url
    assert company.eures_status is EuresStatus.OPENED


async def test_cli_imports_and_reports(capsys: pytest.CaptureFixture[str]) -> None:
    assert await run(SEED) == 0
    assert "982 rows — 982 created, 0 updated, 0 unchanged" in capsys.readouterr().out


async def test_cli_aborts_on_invalid_workbook(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_workbook(tmp_path / "w.xlsx", [row(1, "Numeric A/S", 1234567)])
    assert await run(path) == 1
    assert "workbook invalid" in capsys.readouterr().err
