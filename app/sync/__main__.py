"""Run with:  python -m app.sync PL        (or CL, PD, BL1, SA, FL1, ...)"""
import argparse
import sys

from app.config import settings
from app.database import SessionLocal
from app.sync.client import FootballDataClient
from app.sync.football_data import sync_competition


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync a competition from football-data.org")
    parser.add_argument("code", help="competition code, e.g. PL")
    args = parser.parse_args()

    if not settings.football_data_api_key:
        sys.exit("FOOTBALL_DATA_API_KEY is not set in .env")

    client = FootballDataClient(settings.football_data_api_key)
    with SessionLocal() as db:
        print(f"Syncing {args.code}...")
        report = sync_competition(args.code, client, db)

    print("Created:", report.created or "nothing")
    print("Updated:", report.updated or "nothing")


if __name__ == "__main__":
    main()
