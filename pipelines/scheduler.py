"""APScheduler job definitions (SPEC Section 8, Phase 1 jobs only).

Phase 1 jobs:
- statements_refresh: nightly 02:00 CT (companyfacts -> mapping -> ratios)
- filings_refresh:    nightly 02:30 CT; when it sees a NEW 10-K/10-Q for a
  company it immediately refreshes that company's statements (event-driven
  rule from Section 8).

Later-phase jobs (prices, news, macro, alerts) get added here in their
phases — the run_job wrapper and job_runs bookkeeping are the seam.

Every job run is recorded in job_runs and shown on /status.
"""
from __future__ import annotations

import datetime as dt
import logging
import threading
import traceback
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select

from core.config import settings
from core.db import Company, JobRun, StatementFact, get_session_factory
from pipelines import filings, statements, universe

log = logging.getLogger(__name__)


def run_job(job_name: str, fn: Callable[[], str | None]) -> None:
    """Run fn with job_runs bookkeeping. fn returns an optional summary
    message; exceptions mark the run as error but never propagate (a broken
    job must not take the scheduler down)."""
    factory = get_session_factory()
    with factory() as session:
        run = JobRun(job_name=job_name, started_at=_now(), status="running")
        session.add(run)
        session.commit()
        run_id = run.id
    try:
        message = fn()
        status = "ok"
    except Exception:  # noqa: BLE001
        message = traceback.format_exc(limit=5)
        status = "error"
        log.exception("job %s failed", job_name)
    with factory() as session:
        run = session.get(JobRun, run_id)
        run.finished_at = _now()
        run.status = status
        run.message = (message or "")[:4000]
        session.commit()


def statements_refresh_job(tickers: list[str] | None = None) -> None:
    def work() -> str:
        with get_session_factory()() as session:
            result = statements.refresh_all(session, tickers=tickers)
        return (f"{result['companies']} companies; {len(result['errors'])} errors\n"
                f"{result['coverage']}")
    run_job("statements_refresh", work)


def filings_refresh_job(tickers: list[str] | None = None) -> None:
    def work() -> str:
        with get_session_factory()() as session:
            result = filings.refresh_all(session, tickers=tickers)
            # Event-driven statement refresh for companies with a new 10-K/10-Q
            # (never on first load — see filings.refresh_company).
            triggered = result["new_statements_for"]
            for i, cik in enumerate(triggered, 1):
                try:
                    statements.refresh_company(session, cik)
                    log.info("event refresh [%d/%d] cik=%s ok", i, len(triggered), cik)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    result["errors"].append(f"event refresh {cik}: {exc}")
        return (f"{result['companies']} companies; "
                f"{len(result['new_statements_for'])} triggered statement refreshes; "
                f"{len(result['errors'])} errors")
    run_job("filings_refresh", work)


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=settings.timezone)
    scheduler.add_job(statements_refresh_job, CronTrigger(hour=2, minute=0),
                      id="statements_refresh", name="statements_refresh")
    scheduler.add_job(filings_refresh_job, CronTrigger(hour=2, minute=30),
                      id="filings_refresh", name="filings_refresh")
    return scheduler


def bootstrap_if_needed() -> None:
    """App-startup hook: seed the companies table from the CSV if empty, and
    if there are no statement facts at all, kick off the first full refresh
    in a background thread so `uvicorn app.main:app` is genuinely the one
    command a fresh clone needs (pages show a 'data loading' state until it
    lands)."""
    factory = get_session_factory()
    with factory() as session:
        if session.execute(select(func.count()).select_from(Company)).scalar() == 0:
            universe.load_universe(session)
        has_facts = session.execute(
            select(StatementFact.id).limit(1)
        ).scalar() is not None
    if not has_facts:
        log.info("no statement facts yet — starting initial full refresh in background "
                 "(SEC-throttled; expect ~15-30 minutes for the full universe)")

        def initial_load() -> None:
            filings_refresh_job()
            statements_refresh_job()

        threading.Thread(target=initial_load, name="initial-refresh", daemon=True).start()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)
