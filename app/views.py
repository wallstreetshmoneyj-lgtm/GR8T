"""View-data builders shared by the HTML routes and the /api JSON routes.

Every function returns plain dicts/lists (JSON-serializable after date
stringification) so each page's data is available as JSON with no extra
backend work (SPEC 3). Anything missing renders as "-"/"n/a" — never a 500.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

import markdown as md
import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.format import fmt_ratio, fmt_statement_value, pct_change
from core.config import settings
from core.db import Company, Filing, JobRun, Note, StatementFact
from core.db import Ratio as RatioRow
from pipelines import universe
from pipelines.ratios import CATEGORIES, RATIO_META, RATIO_META_BY_KEY
from pipelines.xbrl_map import DISPLAY_YEARS, ITEM_LABELS, STATEMENT_NAMES, STATEMENTS

DAMODARAN_ATTRIBUTION = "Industry data: Aswath Damodaran, NYU Stern (used with attribution)"
_DAMODARAN_DEFAULT = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datacurrent.html"

FILING_FILTER_CHIPS = [("10-K", "10-K"), ("10-Q", "10-Q"), ("8-K", "8-K"),
                       ("DEF 14A", "DEF 14A"), ("Form 4", "4"), ("All", "")]


# ---------- content files (read once per process; small and static) ----------

_ratio_content: dict[str, dict] | None = None
_damodaran_map: dict | None = None


def ratio_content() -> dict[str, dict]:
    """ratios.yml overlay: owner-editable descriptions/caveats per ratio key."""
    global _ratio_content
    if _ratio_content is None:
        path = settings.content_dir / "ratios.yml"
        entries = yaml.safe_load(path.read_text()) if path.exists() else []
        _ratio_content = {e["key"]: e for e in (entries or []) if isinstance(e, dict) and "key" in e}
    return _ratio_content


def damodaran_url(company: Company) -> str:
    """Per-sector Damodaran link with a generic default; owner refines the
    mapping in data/content/damodaran.yml over time."""
    global _damodaran_map
    if _damodaran_map is None:
        path = settings.content_dir / "damodaran.yml"
        _damodaran_map = yaml.safe_load(path.read_text()) if path.exists() else {}
    sectors = (_damodaran_map or {}).get("sectors", {})
    return sectors.get(company.gics_sector) or (_damodaran_map or {}).get("default", _DAMODARAN_DEFAULT)


# ---------- home / search / sectors ----------

def search_companies(session: Session, q: str, limit: int = 12) -> list[dict]:
    """Ticker-prefix OR name-substring match, case-insensitive (SPEC 9.1)."""
    q = q.strip()
    if not q:
        return []
    pattern_prefix = q.upper() + "%"
    pattern_sub = f"%{q}%"
    rows = session.execute(
        select(Company)
        .where(Company.active)
        .where(Company.ticker.like(pattern_prefix) | Company.name.ilike(pattern_sub))
        .order_by(Company.ticker)
        .limit(limit)
    ).scalars()
    return [{"ticker": c.ticker, "name": c.name, "sector": c.gics_sector} for c in rows]


def sectors(session: Session) -> list[dict]:
    rows = session.execute(
        select(Company.gics_sector, func.count())
        .where(Company.active)
        .group_by(Company.gics_sector)
        .order_by(Company.gics_sector)
    ).all()
    return [{"name": name, "count": count} for name, count in rows]


def sector_companies(session: Session, sector: str) -> list[dict]:
    rows = session.execute(
        select(Company)
        .where(Company.active, Company.gics_sector == sector)
        .order_by(Company.name)
    ).scalars()
    return [{"ticker": c.ticker, "name": c.name, "sub_industry": c.gics_sub_industry}
            for c in rows]


# ---------- company page ----------

def get_company(session: Session, ticker: str) -> Company | None:
    return session.execute(
        select(Company).where(func.upper(Company.ticker) == ticker.upper())
    ).scalar()


def company_header(session: Session, company: Company) -> dict:
    ten_ks = list(session.execute(
        select(Filing).where(Filing.cik == company.cik, Filing.form == "10-K")
        .order_by(Filing.filed_date.desc()).limit(2)
    ).scalars())
    peer_tickers = universe.load_peers().get(company.ticker, [])
    notes_count = session.execute(
        select(func.count()).select_from(Note).where(Note.cik == company.cik)
    ).scalar()
    asof = session.execute(
        select(func.max(StatementFact.fetched_at)).where(StatementFact.cik == company.cik)
    ).scalar()
    return {
        "ticker": company.ticker,
        "name": company.name,
        "cik": company.cik,
        "sector": company.gics_sector,
        "sub_industry": company.gics_sub_industry,
        "ir_url": company.ir_url,
        "active": company.active,
        "peers": peer_tickers,
        "latest_10k": _filing_link(ten_ks[0]) if ten_ks else None,
        "prior_10k": _filing_link(ten_ks[1]) if len(ten_ks) > 1 else None,
        "damodaran_url": damodaran_url(company),
        "damodaran_attribution": DAMODARAN_ATTRIBUTION,
        "notes_count": notes_count or 0,
        "data_as_of": str(asof) if asof else None,
    }


def _filing_link(filing: Filing) -> dict:
    return {"form": filing.form, "filed_date": str(filing.filed_date),
            "url": filing.primary_doc_url}


# ---------- financials tab ----------

def financials_data(session: Session, cik: str) -> dict:
    facts = list(session.execute(
        select(StatementFact).where(StatementFact.cik == cik)
    ).scalars())
    if not facts:
        return {"years": [], "statements": [], "loaded": False}

    by_item: dict[str, dict[int, StatementFact]] = defaultdict(dict)
    for fact in facts:
        by_item[fact.canonical_item][fact.fiscal_year] = fact
    max_fy = max(fact.fiscal_year for fact in facts)
    years = list(range(max_fy, max_fy - DISPLAY_YEARS, -1))  # newest first (SPEC 9.3)

    period_ends: dict[int, str] = {}
    for fact in facts:
        if fact.period_end and fact.fiscal_year not in period_ends:
            period_ends[fact.fiscal_year] = str(fact.period_end)

    statements_out = []
    for statement_code, items in STATEMENTS:
        rows = []
        for item, _chain in items:
            year_facts = by_item.get(item, {})
            if not any(fy in year_facts for fy in years):
                continue  # skip rows entirely null for this company (SPEC 9.3)
            cells = []
            for i, fy in enumerate(years):
                fact = year_facts.get(fy)
                value = fact.value if fact else None
                cells.append({
                    "kind": "value",
                    "fy": fy,
                    "value": value,
                    "display": fmt_statement_value(value, fact.unit if fact else "USD"),
                    "tooltip": (f"{fact.xbrl_tag_used} | {fact.form or 'derived'}"
                                f" filed {fact.filed_date or '-'}") if fact else None,
                })
                if i < len(years) - 1:
                    older_fact = year_facts.get(years[i + 1])
                    change = pct_change(value, older_fact.value if older_fact else None)
                    cells.append({
                        "kind": "pct",
                        "value": change,
                        "display": f"{change * 100:+,.1f}%" if change is not None else "-",
                    })
            rows.append({"item": item, "label": ITEM_LABELS.get(item, item), "cells": cells})
        statements_out.append({
            "code": statement_code,
            "name": STATEMENT_NAMES[statement_code],
            "rows": rows,
        })
    return {
        "years": years,
        "period_ends": period_ends,
        "statements": statements_out,
        "loaded": True,
    }


# ---------- ratios tab ----------

def _ratio_display_meta(key: str) -> dict:
    """Merge code metadata with the ratios.yml overlay (owner's wording wins)."""
    meta = RATIO_META_BY_KEY[key]
    content = ratio_content().get(key, {})
    description = content.get("description") or ""
    if not description or description.startswith("TODO"):
        description = ""  # rendered as "description coming soon" (SPEC 10.3)
    return {
        "key": key,
        "display_name": content.get("display_name") or meta.display_name,
        "category": meta.category,
        "formula": content.get("formula_display") or meta.formula_display,
        "better_when": content.get("better_when") or meta.better_when,
        "description": description,
        "caveats": content.get("caveats") or list(meta.caveats),
        "fmt": meta.fmt,
        "market_data": meta.market_data,
    }


def ratios_data(session: Session, cik: str, category: str | None = None) -> dict:
    ratio_rows = list(session.execute(
        select(RatioRow).where(RatioRow.cik == cik)
    ).scalars())
    by_key: dict[str, dict[int, RatioRow]] = defaultdict(dict)
    for row in ratio_rows:
        by_key[row.ratio_key][row.fiscal_year] = row
    years = sorted({r.fiscal_year for r in ratio_rows}, reverse=True)[:DISPLAY_YEARS]

    categories_out = []
    for cat in CATEGORIES:
        cat_metas = [m for m in RATIO_META if m.category == cat]
        if not cat_metas:
            continue
        fiscal_keys = [m.key for m in cat_metas if not m.market_data]
        market_only = all(m.market_data for m in cat_metas)
        entry = {"name": cat, "count": len(cat_metas), "market_only": market_only,
                 "ratios": []}
        if category == cat:
            for meta in cat_metas:
                display = _ratio_display_meta(meta.key)
                history = []
                for fy in years:
                    row = by_key.get(meta.key, {}).get(fy)
                    history.append(_ratio_cell(row, meta.fmt, fy))
                entry["ratios"].append({**display, "history": history,
                                        "latest": history[0] if history else None})
        else:
            entry["ratio_keys"] = fiscal_keys
        categories_out.append(entry)
    return {"years": years, "categories": categories_out, "selected": category,
            "loaded": bool(ratio_rows)}


def _ratio_cell(row: RatioRow | None, fmt: str, fy: int) -> dict:
    if row is None:
        return {"fy": fy, "value": None, "display": "n/a", "na_reason": "not computed"}
    return {
        "fy": fy,
        "value": row.value,
        "display": fmt_ratio(row.value, fmt) if row.value is not None else "n/a",
        "na_reason": row.na_reason,
    }


def ratio_comps(session: Session, company: Company, ratio_key: str) -> dict | None:
    """Comps view: this company + peers, latest FY value + 5yr history each
    (SPEC 9.4). Peers outside the universe render as such, never break."""
    if ratio_key not in RATIO_META_BY_KEY:
        return None
    meta = RATIO_META_BY_KEY[ratio_key]
    display = _ratio_display_meta(ratio_key)
    tickers = [company.ticker] + universe.load_peers().get(company.ticker, [])
    rows = []
    for ticker in tickers:
        comp = get_company(session, ticker)
        if comp is None:
            rows.append({"ticker": ticker, "name": None, "in_universe": False,
                         "latest": None, "history": []})
            continue
        ratio_rows = {r.fiscal_year: r for r in session.execute(
            select(RatioRow).where(RatioRow.cik == comp.cik, RatioRow.ratio_key == ratio_key)
        ).scalars()}
        years = sorted(ratio_rows, reverse=True)[:DISPLAY_YEARS]
        history = [_ratio_cell(ratio_rows.get(fy), meta.fmt, fy) for fy in years]
        rows.append({
            "ticker": comp.ticker, "name": comp.name, "in_universe": True,
            "latest": history[0] if history else None,
            "history": history,
        })
    return {"ratio": display, "rows": rows}


# ---------- filings tab ----------

def filings_data(session: Session, cik: str, form: str | None = None,
                 limit: int = 1000) -> dict:
    query = select(Filing).where(Filing.cik == cik)
    if form:
        query = query.where(Filing.form == form)
    filings = session.execute(
        query.order_by(Filing.filed_date.desc()).limit(limit)
    ).scalars()
    return {
        "chips": [{"label": label, "form": value} for label, value in FILING_FILTER_CHIPS],
        "selected_form": form or "",
        "filings": [{
            "form": f.form,
            "filed_date": str(f.filed_date),
            "period_of_report": str(f.period_of_report) if f.period_of_report else "-",
            "url": f.primary_doc_url,
        } for f in filings],
    }


# ---------- notes tab ----------

def notes_data(session: Session, cik: str) -> list[dict]:
    notes = session.execute(
        select(Note).where(Note.cik == cik).order_by(Note.created_at.desc())
    ).scalars()
    return [note_dict(n) for n in notes]


def note_dict(note: Note) -> dict:
    return {
        "id": note.id,
        "cik": note.cik,
        "content": note.content,
        # Rendered on display (headings, bold, lists, links — SPEC 9.9).
        # Single-user local tool, so raw-HTML passthrough risk is accepted.
        "html": md.markdown(note.content or "", extensions=["extra"]),
        "created_at": str(note.created_at),
        "updated_at": str(note.updated_at),
    }


# ---------- status page ----------

def status_data(session: Session) -> dict:
    """Last run per job + recent history (SPEC 15)."""
    runs = list(session.execute(
        select(JobRun).order_by(JobRun.started_at.desc()).limit(50)
    ).scalars())
    latest: dict[str, JobRun] = {}
    for run in runs:
        latest.setdefault(run.job_name, run)
    counts = {
        "companies": session.execute(
            select(func.count()).select_from(Company).where(Company.active)).scalar(),
        "statement_facts": session.execute(
            select(func.count()).select_from(StatementFact)).scalar(),
        "ratios": session.execute(select(func.count()).select_from(RatioRow)).scalar(),
        "filings": session.execute(select(func.count()).select_from(Filing)).scalar(),
        "notes": session.execute(select(func.count()).select_from(Note)).scalar(),
    }
    return {
        "jobs": [_job_dict(run) for run in latest.values()],
        "recent_runs": [_job_dict(run) for run in runs[:20]],
        "counts": counts,
        "generated_at": str(dt.datetime.now(dt.UTC).replace(tzinfo=None)),
    }


def _job_dict(run: JobRun) -> dict:
    return {
        "job_name": run.job_name,
        "started_at": str(run.started_at),
        "finished_at": str(run.finished_at) if run.finished_at else None,
        "status": run.status,
        "message": run.message,
    }
