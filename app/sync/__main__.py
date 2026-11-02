"""Run with:  python -m app.sync PL PD CL           sync once
            python -m app.sync PL PD CL --watch   keep results up to date (Ctrl+C to stop)
"""
import argparse
import sys
import time
from datetime import datetime, timezone

from app.config import settings
from app.database import SessionLocal
from app.sync.client import FootballDataClient
from app.sync.football_data import seconds_until_next_sync, sync_competition

TEAMS_REFRESH_SECONDS = 6 * 60 * 60  # squads rarely change, so only re-fetch them every 6 hours


def sync_all(codes: list[str], client: FootballDataClient, include_teams: bool) -> None:
    for code in codes:
        with SessionLocal() as db:
            report = sync_competition(code, client, db, include_teams=include_teams)
        print(f"{code}: created {report.created or 'nothing'}, updated {sum(report.updated.values())} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync competitions from football-data.org")
    parser.add_argument("codes", nargs="+", help="competition codes, e.g. PL PD CL")
    parser.add_argument("--watch", action="store_true", help="keep syncing until stopped")
    args = parser.parse_args()

    if not settings.football_data_api_key:
        sys.exit("FOOTBALL_DATA_API_KEY is not set in .env")
    client = FootballDataClient(settings.football_data_api_key)

    sync_all(args.codes, client, include_teams=True)
    if not args.watch:
        return

    last_teams_sync = time.monotonic()
    while True:
        with SessionLocal() as db:
            wait = seconds_until_next_sync(db, datetime.now(timezone.utc))
        print(f"[{datetime.now():%H:%M:%S}] next sync in {wait // 60}m {wait % 60}s")
        time.sleep(wait)

        refresh_teams = time.monotonic() - last_teams_sync > TEAMS_REFRESH_SECONDS
        if refresh_teams:
            last_teams_sync = time.monotonic()
        try:
            sync_all(args.codes, client, include_teams=refresh_teams)
        except Exception as error:  # a network blip shouldn't stop the watcher; try again next time
            print(f"sync failed, will retry: {error!r}")


if __name__ == "__main__":
    main()
