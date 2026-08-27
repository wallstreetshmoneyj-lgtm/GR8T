"""SQLAlchemy 2.x engine, session factory, and all models (SPEC Section 7).

SQLite in v1, but only portable column types and constraints are used so the
schema can move to Postgres later without changes.

All Section 7 tables are declared now (including Phase 2-4 ones like prices
and econ_observations): the schema is the decided contract, and declaring it
up front is the "clean seam" for later phases. Only Phase 1 tables are
written to by Phase 1 code.

The `notes` table is owner-authored content with a hard rule: NO pipeline
job, refresh, or migration may modify or delete its rows. Enforcement is by
convention (pipelines never import Note) plus the persistence test in
tests/test_notes_persistence.py.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from core.config import settings


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    cik: Mapped[str] = mapped_column(String(10), primary_key=True)  # zero-padded 10 digits
    ticker: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    gics_sector: Mapped[str] = mapped_column(String(60), index=True)
    gics_sub_industry: Mapped[str] = mapped_column(String(80), index=True)
    ir_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class StatementFact(Base):
    """One canonical line-item value for one company fiscal year.

    statement is IS/BS/CF for mapped XBRL facts, or DERIVED for computed
    items (ebitda, fcf, averages, ...) which are stored "like facts" per
    SPEC 10.1 but never rendered in the statement tables.
    """

    __tablename__ = "statement_facts"
    __table_args__ = (UniqueConstraint("cik", "canonical_item", "fiscal_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cik: Mapped[str] = mapped_column(String(10), ForeignKey("companies.cik"), index=True)
    statement: Mapped[str] = mapped_column(String(10))  # IS / BS / CF / DERIVED
    canonical_item: Mapped[str] = mapped_column(String(60))
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    period_end: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="USD")
    xbrl_tag_used: Mapped[str] = mapped_column(String(200))
    form: Mapped[str | None] = mapped_column(String(20), nullable=True)
    filed_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime)


class Ratio(Base):
    __tablename__ = "ratios"
    __table_args__ = (UniqueConstraint("cik", "ratio_key", "fiscal_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cik: Mapped[str] = mapped_column(String(10), ForeignKey("companies.cik"), index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer)
    ratio_key: Mapped[str] = mapped_column(String(50), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    na_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime)


class Filing(Base):
    __tablename__ = "filings"
    # Grain is (company, filing), NOT accession alone: one accession can be
    # filed under several CIKs at once — a spin-off's filings appear under
    # both companies (Abbott/AbbVie), and Form 4s appear under both the
    # issuer and the reporting owner.
    __table_args__ = (UniqueConstraint("cik", "accession"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cik: Mapped[str] = mapped_column(String(10), ForeignKey("companies.cik"), index=True)
    form: Mapped[str] = mapped_column(String(20), index=True)
    filed_date: Mapped[dt.date] = mapped_column(Date, index=True)
    period_of_report: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    accession: Mapped[str] = mapped_column(String(30))
    primary_doc_url: Mapped[str | None] = mapped_column(String(400), nullable=True)


class Price(Base):
    """Phase 2 (delayed quotes)."""

    __tablename__ = "prices"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_abs: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    as_of: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class PriceHistory(Base):
    """Phase 2 (daily closes for later sparklines)."""

    __tablename__ = "price_history"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)


class News(Base):
    """Phase 2 (provider id as pk for dedupe)."""

    __tablename__ = "news"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    headline: Mapped[str] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fetched_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class WatchlistEntry(Base):
    """Phase 2/3."""

    __tablename__ = "watchlist"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    added_at: Mapped[dt.datetime] = mapped_column(DateTime)
    news_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    earnings_alerts: Mapped[bool] = mapped_column(Boolean, default=False)


class Note(Base):
    """Owner-authored research notes. NEVER touched by any job or refresh;
    created/edited/deleted only through the explicit notes UI (SPEC 9.9).
    Keyed by cik (not ticker) so notes survive ticker changes and universe
    removals — the company page URL still resolves the cik via the seed row.
    """

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cik: Mapped[str] = mapped_column(String(10), index=True)  # no FK: notes outlive companies
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime)


class EarningsEvent(Base):
    """Phase 3."""

    __tablename__ = "earnings_calendar"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    event_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    when: Mapped[str | None] = mapped_column(String(10), nullable=True)  # bmo/amc/unknown
    eps_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class EconObservation(Base):
    """Phase 4."""

    __tablename__ = "econ_observations"

    series_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    obs_date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)


class EconRelease(Base):
    """Phase 4."""

    __tablename__ = "econ_releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_name: Mapped[str] = mapped_column(String(120))
    release_date: Mapped[dt.date] = mapped_column(Date, index=True)


class AlertLog(Base):
    """Phase 3 (dedupe so nothing alerts twice)."""

    __tablename__ = "alerts_log"
    __table_args__ = (UniqueConstraint("kind", "ticker", "ref_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20))  # news / earnings
    ticker: Mapped[str] = mapped_column(String(10))
    ref_id: Mapped[str] = mapped_column(String(80))
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(50), index=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running/ok/error
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


# check_same_thread=False: the app serves requests and runs APScheduler jobs
# from different threads; SQLAlchemy's pool + short-lived sessions keep this
# safe, and SQLite handles cross-thread access fine in WAL-less default mode.
_engine = None
_SessionFactory = None
_db_path_override = None  # set only by configure_for_tests


def configure_for_tests(db_path) -> None:
    """Point the engine at a throwaway database file. Tests only."""
    global _engine, _SessionFactory, _db_path_override
    _db_path_override = db_path
    _engine = None
    _SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        db_path = _db_path_override or settings.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory


def create_all() -> None:
    Base.metadata.create_all(get_engine())
