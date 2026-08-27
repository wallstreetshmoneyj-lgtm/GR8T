from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="session")
def orcl_facts() -> dict:
    return load_fixture("companyfacts_ORCL.json")


@pytest.fixture(scope="session")
def msft_facts() -> dict:
    return load_fixture("companyfacts_MSFT.json")


@pytest.fixture(scope="session")
def ibm_facts() -> dict:
    return load_fixture("companyfacts_IBM.json")


@pytest.fixture(scope="session")
def orcl_submissions() -> dict:
    return load_fixture("submissions_ORCL.json")


@pytest.fixture
def db(tmp_path):
    """A throwaway SQLite database per test, with the schema created.

    Yields the session factory (not a session) so tests can open a fresh
    session to simulate an app restart.
    """
    from core import db as core_db

    core_db.configure_for_tests(tmp_path / "test.db")
    core_db.create_all()
    yield core_db.get_session_factory()
    core_db.configure_for_tests(None)


@pytest.fixture
def orcl_company(db):
    """ORCL seeded into the companies table."""
    from core.db import Company

    with db() as session:
        session.add(Company(cik="0001341439", ticker="ORCL", name="Oracle Corporation",
                            gics_sector="Information Technology",
                            gics_sub_industry="Application Software",
                            ir_url=None, active=True))
        session.commit()
    return "0001341439"
