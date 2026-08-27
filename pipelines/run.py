"""CLI for manual pipeline runs: `python -m pipelines.run <command>`.

Commands:
  seed                      create tables + load companies from data/seed/sp500.csv
  refresh [--tickers A,B]   filings + statements refresh (all active companies by default)
  statements [--tickers]    statements refresh only
  filings [--tickers]       filings refresh only
  peers                     generate peers.json (or peers.candidate.json if one exists)
  coverage                  print the latest tag-mapping coverage summary

Add --from-cache to any refresh command to re-parse the cached raw responses
instead of re-fetching from SEC. Use it after fixing a parser: same data, no
new requests (SPEC 6 caches raw bodies for exactly this).
"""
from __future__ import annotations

import argparse
import logging

from core.config import settings
from core.db import create_all, get_session_factory
from pipelines import http_client, scheduler, universe

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

# --from-cache accepts anything fetched in the last 30 days.
CACHE_REUSE_SECONDS = 30 * 24 * 3600


def _tickers(value: str | None) -> list[str] | None:
    return [t.strip().upper() for t in value.split(",")] if value else None


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipelines.run", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("refresh", "statements", "filings"):
        p = sub.add_parser(name)
        p.add_argument("--tickers", help="comma-separated tickers (default: all active)")
        p.add_argument("--from-cache", action="store_true",
                       help="re-parse cached raw responses instead of re-fetching")
    sub.add_parser("seed")
    sub.add_parser("peers")
    sub.add_parser("coverage")
    args = parser.parse_args()

    if getattr(args, "from_cache", False):
        http_client.set_cache_reuse(CACHE_REUSE_SECONDS)

    create_all()
    factory = get_session_factory()

    if args.command == "seed":
        with factory() as session:
            print(universe.load_universe(session))
    elif args.command == "refresh":
        with factory() as session:
            universe.load_universe(session)
        scheduler.filings_refresh_job(_tickers(args.tickers))
        scheduler.statements_refresh_job(_tickers(args.tickers))
    elif args.command == "statements":
        scheduler.statements_refresh_job(_tickers(args.tickers))
    elif args.command == "filings":
        scheduler.filings_refresh_job(_tickers(args.tickers))
    elif args.command == "peers":
        with factory() as session:
            print(universe.write_peers_seed(session))
    elif args.command == "coverage":
        path = settings.reports_dir / "xbrl_coverage_summary.txt"
        print(path.read_text() if path.exists() else "no coverage report yet — run a refresh")


if __name__ == "__main__":
    main()
