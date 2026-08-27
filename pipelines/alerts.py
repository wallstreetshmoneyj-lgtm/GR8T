"""Alert dedupe primitives (SPEC 11).

Phase 3 builds the actual alert engine here: keyword matching over new news
rows, the T-7/T-1/day-of earnings schedule, and SMTP delivery. What exists
now is only the dedupe ledger those will be built on — SPEC 15 requires an
alert-dedupe test, and dedupe is the part that must be right from the start
(a bug here means the owner gets the same alert twice, or misses one).

The guarantee: record_sent() is the single gate. It returns True the first
time an (kind, ticker, ref_id) triple is seen and False forever after, and
the DB's unique constraint makes that hold even if two jobs race.
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.db import AlertLog

log = logging.getLogger(__name__)

NEWS = "news"
EARNINGS = "earnings"

# SPEC 11 default keyword filter (config-editable in Phase 3).
DEFAULT_NEWS_KEYWORDS = [
    "earnings", "guidance", "outlook", "acquisition", "acquire", "merger",
    "downgrade", "upgrade", "investigation", "SEC", "subpoena", "resign",
    "CEO", "CFO", "dividend", "buyback", "repurchase", "restructuring",
    "layoffs", "bankruptcy", "default",
]


def record_sent(session: Session, kind: str, ticker: str, ref_id: str) -> bool:
    """Claim an alert. True = this is new and the caller should send it;
    False = already alerted, skip.

    Claim before sending, not after: a crash between send and log would
    otherwise re-alert on the next run.
    """
    entry = AlertLog(kind=kind, ticker=ticker.upper(), ref_id=str(ref_id),
                     sent_at=dt.datetime.now(dt.UTC).replace(tzinfo=None))
    session.add(entry)
    try:
        session.commit()
        return True
    except IntegrityError:
        # Unique constraint on (kind, ticker, ref_id) — already claimed.
        session.rollback()
        return False


def earnings_ref_id(event_date: dt.date, offset_days: int) -> str:
    """Stable id for one earnings reminder, so T-7/T-1/day-of each alert
    once per event and re-runs in the same window never duplicate."""
    return f"{event_date.isoformat()}:T-{offset_days}"


def headline_matches(headline: str, keywords: list[str] | None = None) -> bool:
    """Case-insensitive keyword filter for news alerts (SPEC 11)."""
    text = (headline or "").lower()
    return any(kw.lower() in text for kw in (keywords or DEFAULT_NEWS_KEYWORDS))
