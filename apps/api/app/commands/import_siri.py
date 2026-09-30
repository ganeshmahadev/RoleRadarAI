"""Import the SIRI seed workbook.

    uv run python -m app.commands.import_siri ../../data/siri_certified_companies_eures_queue.xlsx
    docker compose exec api python -m app.commands.import_siri \
        /data/siri_certified_companies_eures_queue.xlsx
"""

import argparse
import asyncio
import sys
from pathlib import Path

from app.db.session import get_engine, get_sessionmaker
from app.services.siri_import import SiriImportError, import_siri_companies, read_siri_workbook


async def run(path: Path) -> int:
    try:
        rows = read_siri_workbook(path)
    except SiriImportError as exc:
        print(f"Import aborted, workbook invalid ({len(exc.errors)} errors):", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    async with get_sessionmaker()() as session:
        result = await import_siri_companies(session, rows)
    await get_engine().dispose()
    print(
        f"SIRI import: {result.total} rows — {result.created} created, "
        f"{result.updated} updated, {result.unchanged} unchanged"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.workbook)))


if __name__ == "__main__":
    main()
