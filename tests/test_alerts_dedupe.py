"""Alert dedupe tests (SPEC 15). Delivery itself is Phase 3; the dedupe
ledger these cover is what guarantees nothing alerts twice."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from core.db import AlertLog
from pipelines import alerts


def test_first_claim_wins_and_repeat_is_refused(db):
    with db() as session:
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "news-123") is True
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "news-123") is False
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "news-123") is False


def test_only_one_row_is_written_per_alert(db):
    with db() as session:
        for _ in range(5):
            alerts.record_sent(session, alerts.NEWS, "ORCL", "news-123")
        count = session.execute(select(func.count()).select_from(AlertLog)).scalar()
    assert count == 1


def test_different_articles_alert_independently(db):
    with db() as session:
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "news-1") is True
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "news-2") is True


def test_same_ref_on_different_tickers_alerts_independently(db):
    # Providers can reuse ids across tickers; the ticker is part of the key.
    with db() as session:
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "shared-id") is True
        assert alerts.record_sent(session, alerts.NEWS, "MSFT", "shared-id") is True


def test_news_and_earnings_kinds_do_not_collide(db):
    with db() as session:
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "2026-09-10") is True
        assert alerts.record_sent(session, alerts.EARNINGS, "ORCL", "2026-09-10") is True


def test_earnings_reminders_fire_once_per_offset(db):
    event = dt.date(2026, 9, 10)
    with db() as session:
        for offset in (7, 1, 0):
            ref = alerts.earnings_ref_id(event, offset)
            assert alerts.record_sent(session, alerts.EARNINGS, "ORCL", ref) is True
        # An hourly job re-running inside the same window must not re-alert.
        for offset in (7, 1, 0):
            ref = alerts.earnings_ref_id(event, offset)
            assert alerts.record_sent(session, alerts.EARNINGS, "ORCL", ref) is False


def test_next_quarters_event_is_a_separate_alert(db):
    with db() as session:
        first = alerts.earnings_ref_id(dt.date(2026, 9, 10), 7)
        second = alerts.earnings_ref_id(dt.date(2026, 12, 10), 7)
        assert alerts.record_sent(session, alerts.EARNINGS, "ORCL", first) is True
        assert alerts.record_sent(session, alerts.EARNINGS, "ORCL", second) is True


def test_dedupe_survives_a_new_session(db):
    with db() as session:
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "news-123") is True
    with db() as session:  # next hourly run, fresh session
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "news-123") is False


def test_ticker_case_does_not_create_a_duplicate(db):
    with db() as session:
        assert alerts.record_sent(session, alerts.NEWS, "orcl", "news-9") is True
        assert alerts.record_sent(session, alerts.NEWS, "ORCL", "news-9") is False


class TestKeywordFilter:
    def test_matches_are_case_insensitive(self):
        assert alerts.headline_matches("Oracle raises full-year GUIDANCE")
        assert alerts.headline_matches("Oracle announces a buyback")

    def test_unrelated_headline_does_not_match(self):
        assert not alerts.headline_matches("Oracle opens a new campus in Nashville")

    def test_custom_keyword_list_is_honored(self):
        assert alerts.headline_matches("RPO backlog surges", ["rpo"])
        assert not alerts.headline_matches("RPO backlog surges", ["dividend"])
