"""Notes persistence guarantees (SPEC 9.9, 15).

The rule these tests defend: NO job, refresh, or migration may ever modify
or delete a note row. Deletion happens only through the explicit UI action.
These run the real statements_refresh and filings_refresh against the same
company the notes belong to and assert the rows are byte-identical after.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from core.db import Company, Note, StatementFact
from pipelines import filings, statements


def _snapshot(factory) -> list[tuple]:
    with factory() as session:
        return [(n.id, n.cik, n.content, n.created_at, n.updated_at)
                for n in session.execute(select(Note).order_by(Note.id)).scalars()]


def _add_notes(factory, cik: str) -> list[tuple]:
    now = dt.datetime(2026, 8, 1, 12, 0, 0)
    with factory() as session:
        session.add(Note(cik=cik, content="# ORCL thesis\n\nRPO growth is the tell.",
                         created_at=now, updated_at=now))
        session.add(Note(cik=cik, content="Second note: watch the capex cycle.",
                         created_at=now, updated_at=now))
        session.commit()
    return _snapshot(factory)


def test_notes_survive_statements_refresh(db, orcl_company, orcl_facts):
    before = _add_notes(db, orcl_company)
    assert len(before) == 2

    with db() as session:
        statements.refresh_company(session, orcl_company, facts_json=orcl_facts)
        # sanity: the refresh really did write facts for this company
        assert session.execute(
            select(StatementFact).where(StatementFact.cik == orcl_company)
        ).first() is not None

    assert _snapshot(db) == before


def test_notes_survive_filings_refresh(db, orcl_company, orcl_submissions):
    before = _add_notes(db, orcl_company)

    with db() as session:
        filings.refresh_company(session, orcl_company, subs_json=orcl_submissions)

    assert _snapshot(db) == before


def test_notes_survive_repeated_full_refreshes(db, orcl_company, orcl_facts,
                                               orcl_submissions):
    before = _add_notes(db, orcl_company)

    # Statement facts are deleted and rebuilt on every refresh — the notes
    # table must be entirely unaffected by that churn, run after run.
    for _ in range(3):
        with db() as session:
            filings.refresh_company(session, orcl_company, subs_json=orcl_submissions)
            statements.refresh_company(session, orcl_company, facts_json=orcl_facts)

    assert _snapshot(db) == before


def test_notes_survive_an_app_restart(db, orcl_company):
    before = _add_notes(db, orcl_company)

    # Simulate a restart: drop the engine/session factory and rebuild them
    # against the same file, the way a fresh process would.
    from core import db as core_db

    path = core_db._db_path_override
    core_db.configure_for_tests(path)
    core_db.create_all()

    assert _snapshot(core_db.get_session_factory()) == before


def test_notes_outlive_removal_from_the_universe(db, orcl_company, orcl_facts):
    """"If a company is removed from the seed file, its notes remain
    readable at its URL" — universe sync deactivates, never deletes."""
    before = _add_notes(db, orcl_company)

    with db() as session:
        company = session.get(Company, orcl_company)
        company.active = False  # what load_universe() does on a dropped ticker
        session.commit()

    after = _snapshot(db)
    assert after == before
    with db() as session:
        # still resolvable by cik for the company page
        assert session.get(Company, orcl_company) is not None


def test_deletion_only_removes_the_targeted_note(db, orcl_company):
    _add_notes(db, orcl_company)
    with db() as session:
        first = session.execute(select(Note).order_by(Note.id)).scalars().first()
        session.delete(first)  # the one explicit deletion path (API delete_note)
        session.commit()

    remaining = _snapshot(db)
    assert len(remaining) == 1
    assert "capex cycle" in remaining[0][2]
