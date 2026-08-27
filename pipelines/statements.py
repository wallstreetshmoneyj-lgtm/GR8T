"""Build 5-year statements: fetch companyfacts, map to canonical items,
compute derived items, store, and trigger the ratio recompute.

Derived items (SPEC 10.1) are stored in statement_facts with
statement='DERIVED' so ratios and future features read one table. They are
never rendered in the statement tables (those render only the IS/BS/CF
canonical lists).

Missing-component conventions for derived sums, chosen once and documented:
- total_debt: null only when BOTH short_term_debt and long_term_debt are
  unmapped; a single missing side counts as 0 (companies with no ST debt
  simply don't report the tag).
- net_debt / invested_capital: a null total_debt or missing st_investments/
  cash counts as 0 (same reasoning); invested_capital requires total_equity.
- fcf: requires BOTH cfo and capex. A missing capex usually means the
  business doesn't report one (banks) — fcf is left null rather than
  silently equal to cfo.
"""
from __future__ import annotations

import csv
import datetime as dt
import logging
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.config import settings
from core.db import Company, StatementFact
from pipelines import edgar_client, ratios, xbrl_map
from pipelines.xbrl_map import DISPLAY_YEARS, MappedFact, ParseResult

log = logging.getLogger(__name__)


@dataclass
class Derived:
    item: str
    fiscal_year: int
    value: float | None
    formula: str
    unit: str = "USD"


def refresh_company(session: Session, cik: str, facts_json: dict | None = None) -> ParseResult:
    """Full statement rebuild for one company. Replaces the company's
    statement_facts rows (mapped + derived), then recomputes ratios.
    Touches nothing else — notes are in a separate table this module
    never imports."""
    if facts_json is None:
        facts_json = edgar_client.fetch_companyfacts(cik)
    result = xbrl_map.parse_companyfacts(facts_json)
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)

    session.execute(delete(StatementFact).where(StatementFact.cik == cik))
    for fact in result.facts:
        session.add(StatementFact(
            cik=cik, statement=fact.statement, canonical_item=fact.item,
            fiscal_year=fact.fiscal_year, period_end=fact.period_end,
            value=fact.value, unit=fact.unit, xbrl_tag_used=fact.tag,
            form=fact.form, filed_date=fact.filed, fetched_at=now,
        ))
    for d in _compute_derived(result):
        if d.value is None:
            continue
        session.add(StatementFact(
            cik=cik, statement="DERIVED", canonical_item=d.item,
            fiscal_year=d.fiscal_year, period_end=_period_end_for(result, d.fiscal_year),
            value=d.value, unit=d.unit, xbrl_tag_used=f"derived:{d.formula}",
            form=None, filed_date=None, fetched_at=now,
        ))
    session.commit()
    ratios.recompute_company(session, cik)
    return result


def _period_end_for(result: ParseResult, fy: int) -> dt.date | None:
    for fact in result.facts:
        if fact.fiscal_year == fy:
            return fact.period_end
    return None


def _pivot(result: ParseResult) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for fact in result.facts:
        out.setdefault(fact.item, {})[fact.fiscal_year] = fact.value
    return out


def _compute_derived(result: ParseResult) -> list[Derived]:
    v = _pivot(result)

    def get(item: str, fy: int) -> float | None:
        return v.get(item, {}).get(fy)

    derived: list[Derived] = []
    base: dict[str, dict[int, float | None]] = {}

    def put(item: str, fy: int, value: float | None, formula: str, unit: str = "USD") -> None:
        base.setdefault(item, {})[fy] = value
        derived.append(Derived(item, fy, value, formula, unit))

    # Base derived items for every stored year (the extra prior year feeds
    # the averages of the oldest displayed year).
    for fy in result.fiscal_years:
        op, dna = get("operating_income", fy), get("d_and_a", fy)
        put("ebit", fy, op, "operating_income")
        # ebitda = operating income + D&A. An approximation: D&A from the
        # cash flow statement can include amounts embedded in COGS.
        put("ebitda", fy, None if op is None or dna is None else op + dna,
            "operating_income+d_and_a (approximation)")

        std, ltd = get("short_term_debt", fy), get("long_term_debt", fy)
        total_debt = None if std is None and ltd is None else (std or 0.0) + (ltd or 0.0)
        put("total_debt", fy, total_debt, "short_term_debt+long_term_debt")

        cash, sti = get("cash", fy), get("st_investments", fy)
        net_debt = None if cash is None else (total_debt or 0.0) - cash - (sti or 0.0)
        put("net_debt", fy, net_debt, "total_debt-cash-st_investments")

        tax, pretax = get("income_tax_expense", fy), get("pretax_income", fy)
        etr = None
        if tax is not None and pretax is not None and pretax > 0:
            etr = tax / pretax
        put("effective_tax_rate", fy, etr, "income_tax_expense/pretax_income", unit="ratio")
        put("nopat", fy, None if op is None or etr is None else op * (1 - etr),
            "ebit*(1-effective_tax_rate)")

        equity = get("total_equity", fy)
        ic = None
        if equity is not None:
            ic = (total_debt or 0.0) + equity - (cash or 0.0) - (sti or 0.0)
        put("invested_capital", fy, ic, "total_debt+total_equity-cash-st_investments")

        cfo, capex = get("cfo", fy), get("capex", fy)
        put("fcf", fy, None if cfo is None or capex is None else cfo - capex, "cfo-capex")

        ca, cl = get("current_assets", fy), get("current_liabilities", fy)
        put("working_capital", fy, None if ca is None or cl is None else ca - cl,
            "current_assets-current_liabilities")

    # Two-point averages (current + prior FY; current alone when prior is
    # missing). avg_ppe is included because fixed_asset_turnover needs it
    # (SPEC 10.2 uses "avg ppe" though 10.1's list omits it).
    avg_sources = {
        "avg_assets": "total_assets", "avg_equity": "total_equity",
        "avg_ar": "accounts_receivable", "avg_inventory": "inventory",
        "avg_ap": "accounts_payable", "avg_ppe": "ppe_net",
    }
    display = result.fiscal_years[:DISPLAY_YEARS]
    for fy in display:
        for avg_item, source in avg_sources.items():
            cur, prior = get(source, fy), get(source, fy - 1)
            value = None if cur is None else (cur if prior is None else (cur + prior) / 2)
            put(avg_item, fy, value, f"mean({source} FY,FY-1)")
        cur = base.get("invested_capital", {}).get(fy)
        prior = base.get("invested_capital", {}).get(fy - 1)
        put("avg_ic", fy, None if cur is None else (cur if prior is None else (cur + prior) / 2),
            "mean(invested_capital FY,FY-1)")
    return derived


def refresh_all(session: Session, tickers: list[str] | None = None) -> dict:
    """Batch refresh (nightly job / CLI). One failure never kills the batch.
    Writes the tag-mapping coverage report the owner reviews (SPEC 10.1)."""
    query = select(Company).where(Company.active).order_by(Company.ticker)
    companies = list(session.execute(query).scalars())
    if tickers:
        wanted = {t.upper() for t in tickers}
        companies = [c for c in companies if c.ticker in wanted]

    coverage_rows: list[dict] = []
    errors: list[str] = []
    for i, company in enumerate(companies, 1):
        try:
            result = refresh_company(session, company.cik)
            for item in result.missing_items:
                coverage_rows.append({"ticker": company.ticker, "item": item})
            log.info("[%d/%d] %s ok (%d facts, %d unmapped items)",
                     i, len(companies), company.ticker, len(result.facts),
                     len(result.missing_items))
        except Exception as exc:  # noqa: BLE001 — batch must survive one bad company
            session.rollback()
            errors.append(f"{company.ticker}: {exc}")
            log.warning("[%d/%d] %s FAILED: %s", i, len(companies), company.ticker, exc)

    summary = _write_coverage_report(coverage_rows, [c.ticker for c in companies], errors)
    return {"companies": len(companies), "errors": errors, "coverage": summary}


def _write_coverage_report(rows: list[dict], tickers: list[str], errors: list[str]) -> str:
    """data/reports/xbrl_coverage.csv: every (company, item) with no mapped
    value in the display window, plus a summary with the core-item metric."""
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = settings.reports_dir / "xbrl_coverage.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "item"])
        writer.writeheader()
        writer.writerows(rows)

    n = len(tickers)
    core_cells = n * len(xbrl_map.CORE_ITEMS)
    core_missing = sum(1 for r in rows if r["item"] in xbrl_map.CORE_ITEMS)
    pct = (100.0 * core_missing / core_cells) if core_cells else 0.0
    summary = (
        f"companies: {n}\n"
        f"core-item cells missing: {core_missing}/{core_cells} ({pct:.1f}%)  "
        f"[target < 10%]\n"
        f"all unmapped (company,item) pairs: {len(rows)}\n"
        f"fetch/parse errors: {len(errors)}\n"
    )
    (settings.reports_dir / "xbrl_coverage_summary.txt").write_text(
        summary + ("\nerrors:\n" + "\n".join(errors) + "\n" if errors else "")
    )
    return summary


def statement_facts_asof(session: Session, cik: str) -> dt.datetime | None:
    """Newest fetched_at for a company's facts (page footer 'data as of')."""
    row = session.execute(
        select(StatementFact.fetched_at).where(StatementFact.cik == cik)
        .order_by(StatementFact.fetched_at.desc()).limit(1)
    ).scalar()
    return row


def load_items(session: Session, cik: str) -> dict[str, dict[int, StatementFact]]:
    """item -> fiscal_year -> row, for views and the ratio engine."""
    out: dict[str, dict[int, StatementFact]] = {}
    for fact in session.execute(
        select(StatementFact).where(StatementFact.cik == cik)
    ).scalars():
        out.setdefault(fact.canonical_item, {})[fact.fiscal_year] = fact
    return out
