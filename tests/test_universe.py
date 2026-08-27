"""Universe seed loading and peer auto-seeding (SPEC 5, 12)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from core.db import Company, Note, StatementFact
from pipelines import universe

HEADER = "ticker,company_name,cik,gics_sector,gics_sub_industry,ir_url,active\n"


def write_csv(tmp_path, rows: list[str]):
    path = tmp_path / "sp500.csv"
    path.write_text(HEADER + "".join(r + "\n" for r in rows))
    return path


def test_load_seeds_companies_and_pads_cik(db, tmp_path):
    csv_path = write_csv(tmp_path, [
        "ORCL,Oracle Corporation,1341439,Information Technology,Application Software,,true",
    ])
    with db() as session:
        result = universe.load_universe(session, csv_path)
        company = session.execute(select(Company)).scalars().one()

    assert result["added"] == 1
    assert company.cik == "0001341439"  # zero-padded to 10 digits
    assert company.ir_url is None  # blank renders fine (SPEC 5)


def test_reload_updates_in_place_without_duplicating(db, tmp_path):
    first = write_csv(tmp_path, [
        "ORCL,Oracle Corporation,0001341439,Information Technology,Application Software,,true",
    ])
    second = write_csv(tmp_path, [
        "ORCL,Oracle Corp,0001341439,Information Technology,Systems Software,https://investor.oracle.com,true",
    ])
    with db() as session:
        universe.load_universe(session, first)
        result = universe.load_universe(session, second)
        company = session.execute(select(Company)).scalars().one()

    assert result["updated"] == 1
    assert company.name == "Oracle Corp"
    assert company.gics_sub_industry == "Systems Software"
    assert company.ir_url == "https://investor.oracle.com"  # owner edits are picked up


def test_dropped_company_is_deactivated_never_deleted(db, tmp_path):
    """A company leaving the index keeps its row, its facts, and its notes —
    the page must stay readable at its URL (SPEC 9.9)."""
    both = write_csv(tmp_path, [
        "ORCL,Oracle Corporation,0001341439,Information Technology,Application Software,,true",
        "XYZ,Gone Inc,0000000123,Industrials,Machinery,,true",
    ])
    only_one = tmp_path / "sp500_reduced.csv"
    only_one.write_text(HEADER +
                        "ORCL,Oracle Corporation,0001341439,Information Technology,Application Software,,true\n")

    with db() as session:
        universe.load_universe(session, both)
        now = dt.datetime(2026, 8, 1)
        session.add(Note(cik="0000000123", content="notes on the delisted one",
                         created_at=now, updated_at=now))
        session.commit()

        result = universe.load_universe(session, only_one)
        dropped = session.get(Company, "0000000123")
        note = session.execute(select(Note)).scalars().one()

    assert result["deactivated"] == 1
    assert dropped is not None and dropped.active is False
    assert note.content == "notes on the delisted one"


def test_missing_seed_file_fails_loudly(db, tmp_path):
    with db() as session:
        try:
            universe.load_universe(session, tmp_path / "nope.csv")
        except FileNotFoundError as exc:
            assert "refresh-universe" in str(exc)  # tells the owner what to run
        else:
            raise AssertionError("expected FileNotFoundError")


class TestPeerGeneration:
    @staticmethod
    def _seed(session, rows: list[tuple[str, str, str, float | None]]) -> None:
        """rows: (ticker, cik, sub_industry, latest revenue or None)"""
        for ticker, cik, sub_industry, revenue in rows:
            session.add(Company(cik=cik, ticker=ticker, name=f"{ticker} Inc",
                                gics_sector="Information Technology",
                                gics_sub_industry=sub_industry, active=True))
            if revenue is not None:
                session.add(StatementFact(
                    cik=cik, statement="IS", canonical_item="revenue", fiscal_year=2026,
                    period_end=dt.date(2026, 5, 31), value=revenue, unit="USD",
                    xbrl_tag_used="Revenues", form="10-K",
                    filed_date=dt.date(2026, 6, 22), fetched_at=dt.datetime(2026, 8, 1)))
        session.commit()

    def test_peers_are_largest_sub_industry_siblings_by_revenue(self, db):
        with db() as session:
            self._seed(session, [
                ("AAA", "0000000001", "Application Software", 10e9),
                ("BBB", "0000000002", "Application Software", 50e9),
                ("CCC", "0000000003", "Application Software", 30e9),
                ("DDD", "0000000004", "Application Software", 40e9),
                ("EEE", "0000000005", "Application Software", 20e9),
                ("FFF", "0000000006", "Application Software", 5e9),
                ("ZZZ", "0000000009", "Systems Software", 99e9),
            ])
            peers = universe.generate_peers(session)

        # 4 largest siblings, biggest first; never itself, never another sub-industry
        assert peers["AAA"] == ["BBB", "DDD", "CCC", "EEE"]
        assert "AAA" not in peers["AAA"]
        assert "ZZZ" not in peers["AAA"]

    def test_sub_industry_with_few_members_returns_what_exists(self, db):
        with db() as session:
            self._seed(session, [
                ("AAA", "0000000001", "Application Software", 10e9),
                ("BBB", "0000000002", "Application Software", 20e9),
                ("SOLO", "0000000007", "Water Utilities", 1e9),
            ])
            peers = universe.generate_peers(session)

        assert peers["AAA"] == ["BBB"]
        assert peers["SOLO"] == []  # renders fine as an empty comps row

    def test_companies_without_revenue_sort_last_not_dropped(self, db):
        with db() as session:
            self._seed(session, [
                ("AAA", "0000000001", "Application Software", 10e9),
                ("BBB", "0000000002", "Application Software", None),
                ("CCC", "0000000003", "Application Software", 30e9),
            ])
            peers = universe.generate_peers(session)

        assert peers["AAA"] == ["CCC", "BBB"]

    def test_owner_overrides_win(self, db):
        """SPEC 17.3: ORCL's peer set is hand-tuned to MSFT/IBM/CRM/SAP."""
        with db() as session:
            self._seed(session, [
                ("ORCL", "0001341439", "Application Software", 67e9),
                ("AAA", "0000000001", "Application Software", 10e9),
            ])
            peers = universe.generate_peers(session)

        assert peers["ORCL"] == ["MSFT", "IBM", "CRM", "SAP"]

    def test_existing_peers_file_is_never_overwritten(self, db, tmp_path, monkeypatch):
        peers_path = tmp_path / "peers.json"
        peers_path.write_text('{"ORCL": ["HAND", "TUNED"]}\n')
        monkeypatch.setattr(universe, "PEERS_JSON", peers_path)

        with db() as session:
            self._seed(session, [("ORCL", "0001341439", "Application Software", 67e9)])
            written = universe.write_peers_seed(session)

        assert written.name == "peers.candidate.json"  # candidate, for review
        assert peers_path.read_text() == '{"ORCL": ["HAND", "TUNED"]}\n'  # untouched
