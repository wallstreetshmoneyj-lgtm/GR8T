"""Filings pipeline tests: link building, event-driven refresh triggers, and
the shared-accession case that a naive unique constraint gets wrong."""
from __future__ import annotations

import copy

from sqlalchemy import select

from core.db import Company, Filing
from pipelines import filings


def _one_filing(accession: str, form: str = "8-K", filed: str = "2026-02-10") -> dict:
    return {"filings": {"recent": {
        "accessionNumber": [accession],
        "form": [form],
        "filingDate": [filed],
        "reportDate": [filed],
        "primaryDocument": ["doc.htm"],
    }}}


def test_two_companies_can_share_one_accession(db):
    """Abbott and AbbVie (its spin-off) file under one accession; the same
    happens for any Form 4 carrying issuer + reporting owner. Both company
    rows must be stored — the unique grain is (cik, accession)."""
    with db() as session:
        session.add(Company(cik="0000001800", ticker="ABT", name="Abbott",
                            gics_sector="Health Care", gics_sub_industry="Health Care Equipment"))
        session.add(Company(cik="0001551152", ticker="ABBV", name="AbbVie",
                            gics_sector="Health Care", gics_sub_industry="Biotechnology"))
        session.commit()

        shared = _one_filing("0000001800-26-000012")
        filings.refresh_company(session, "0000001800", subs_json=copy.deepcopy(shared))
        filings.refresh_company(session, "0001551152", subs_json=copy.deepcopy(shared))

        rows = list(session.execute(select(Filing)).scalars())

    assert len(rows) == 2
    assert {r.cik for r in rows} == {"0000001800", "0001551152"}


def test_repeat_refresh_is_idempotent(db, orcl_company, orcl_submissions):
    with db() as session:
        filings.refresh_company(session, orcl_company, subs_json=copy.deepcopy(orcl_submissions))
        first = session.execute(select(Filing)).scalars().all()
        filings.refresh_company(session, orcl_company, subs_json=copy.deepcopy(orcl_submissions))
        second = session.execute(select(Filing)).scalars().all()
    assert len(first) == len(second) > 0


def test_duplicate_accession_within_one_payload_is_stored_once(db, orcl_company):
    """Older submission history files can overlap when merged."""
    payload = {"filings": {"recent": {
        "accessionNumber": ["0001341439-26-000001", "0001341439-26-000001"],
        "form": ["10-K", "10-K"],
        "filingDate": ["2026-06-22", "2026-06-22"],
        "reportDate": ["2026-05-31", "2026-05-31"],
        "primaryDocument": ["orcl.htm", "orcl.htm"],
    }}}
    with db() as session:
        filings.refresh_company(session, orcl_company, subs_json=payload)
        assert len(session.execute(select(Filing)).scalars().all()) == 1


def test_new_10k_triggers_a_statement_refresh(db, orcl_company):
    with db() as session:
        triggered = filings.refresh_company(
            session, orcl_company, subs_json=_one_filing("0001341439-26-000001", form="10-K"))
        assert triggered == ["10-K"]
        # Already seen on the next run -> no re-trigger.
        assert filings.refresh_company(
            session, orcl_company,
            subs_json=_one_filing("0001341439-26-000001", form="10-K")) == []


def test_routine_forms_do_not_trigger_a_statement_refresh(db, orcl_company):
    with db() as session:
        assert filings.refresh_company(
            session, orcl_company, subs_json=_one_filing("0001341439-26-000009", form="4")) == []


def test_document_url_points_at_edgar_archives(db, orcl_company):
    with db() as session:
        filings.refresh_company(session, orcl_company,
                                subs_json=_one_filing("0001341439-26-000001", form="10-K"))
        row = session.execute(select(Filing)).scalars().one()
    # cik without zero padding, accession without dashes (SPEC 6)
    assert row.primary_doc_url == (
        "https://www.sec.gov/Archives/edgar/data/1341439/000134143926000001/doc.htm")


def test_rows_with_unparseable_dates_are_skipped_not_fatal(db, orcl_company):
    payload = {"filings": {"recent": {
        "accessionNumber": ["0001341439-26-000001", "0001341439-26-000002"],
        "form": ["10-K", "8-K"],
        "filingDate": ["", "2026-02-10"],  # first row unusable
        "reportDate": ["2026-05-31", ""],
        "primaryDocument": ["a.htm", "b.htm"],
    }}}
    with db() as session:
        filings.refresh_company(session, orcl_company, subs_json=payload)
        rows = session.execute(select(Filing)).scalars().all()
    assert [r.form for r in rows] == ["8-K"]
    assert rows[0].period_of_report is None


def test_latest_10ks_returns_newest_first(db, orcl_company, orcl_submissions):
    with db() as session:
        filings.refresh_company(session, orcl_company, subs_json=orcl_submissions)
        latest = filings.latest_10ks(session, orcl_company, count=2)
    assert len(latest) == 2
    assert latest[0].filed_date > latest[1].filed_date
