"""Filing index: SEC submissions JSON -> filings table (links only, never
document mirroring).

filings_refresh also reports which companies got a NEW 10-K or 10-Q so the
scheduler can trigger an event-driven statements refresh for just those
companies (SPEC Section 8).
"""
from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db import Company, Filing
from pipelines import edgar_client

log = logging.getLogger(__name__)

STATEMENT_TRIGGER_FORMS = {"10-K", "10-Q"}


def refresh_company(session: Session, cik: str, subs_json: dict | None = None) -> list[str]:
    """Upsert all filings for one company. Returns the forms of newly seen
    10-K/10-Q filings (empty list when nothing new)."""
    if subs_json is None:
        subs_json = edgar_client.fetch_submissions(cik)
    recent = subs_json.get("filings", {}).get("recent", {})

    existing = set(
        session.execute(select(Filing.accession).where(Filing.cik == cik)).scalars()
    )
    new_trigger_forms: list[str] = []

    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filed_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    primary_docs = recent.get("primaryDocument", [])
    for i, accession in enumerate(accessions):
        if accession in existing:
            continue
        # Also guards against the same accession appearing twice inside one
        # company's merged history (older submission files can overlap).
        existing.add(accession)
        form = forms[i] if i < len(forms) else ""
        filed = _parse_date(filed_dates[i] if i < len(filed_dates) else None)
        if not form or filed is None:
            continue
        period = _parse_date(report_dates[i] if i < len(report_dates) else None)
        primary_doc = primary_docs[i] if i < len(primary_docs) else ""
        url = edgar_client.archive_doc_url(cik, accession, primary_doc) if primary_doc else None
        session.add(Filing(cik=cik, form=form, filed_date=filed, period_of_report=period,
                           accession=accession, primary_doc_url=url))
        if form in STATEMENT_TRIGGER_FORMS:
            new_trigger_forms.append(form)
    session.commit()
    return new_trigger_forms


def refresh_all(session: Session, tickers: list[str] | None = None) -> dict:
    """Nightly filings job. Returns per-company new-10-K/10-Q info so the
    caller can trigger statement refreshes."""
    query = select(Company).where(Company.active).order_by(Company.ticker)
    companies = list(session.execute(query).scalars())
    if tickers:
        wanted = {t.upper() for t in tickers}
        companies = [c for c in companies if c.ticker in wanted]

    needs_statement_refresh: list[str] = []
    errors: list[str] = []
    for i, company in enumerate(companies, 1):
        try:
            new_forms = refresh_company(session, company.cik)
            if new_forms:
                needs_statement_refresh.append(company.cik)
            log.info("[%d/%d] filings %s ok%s", i, len(companies), company.ticker,
                     f" (new: {new_forms})" if new_forms else "")
        except Exception as exc:  # noqa: BLE001 — batch survives one bad company
            session.rollback()
            errors.append(f"{company.ticker}: {exc}")
            log.warning("filings %s FAILED: %s", company.ticker, exc)
    return {"companies": len(companies), "new_statements_for": needs_statement_refresh,
            "errors": errors}


def latest_10ks(session: Session, cik: str, count: int = 2) -> list[Filing]:
    """Newest 10-Ks for the links row (latest + prior)."""
    return list(session.execute(
        select(Filing).where(Filing.cik == cik, Filing.form == "10-K")
        .order_by(Filing.filed_date.desc()).limit(count)
    ).scalars())


def _parse_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None
