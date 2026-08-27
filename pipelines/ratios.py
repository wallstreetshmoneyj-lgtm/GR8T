"""Ratio engine (SPEC 10.2) + ratio metadata shared with ratios.yml.

Fiscal-data ratios are computed per company per fiscal year from
statement_facts and stored in the ratios table with na_reason when inputs
are missing or a denominator rule fires.

Market-data ratios (SPEC 10.2 second list) are Phase 2 on pages, but the
math lives here now as pure functions so the golden tests can cover EV math
with a stubbed price and Phase 2 only has to wire prices in.

compute_fiscal_ratios is deliberately one straight-line function in the
same order as SPEC 10.2 — it reads like the spec, which beats a clever
registry for a solo maintainer.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.db import Ratio, StatementFact

DAYS_PER_YEAR = 365.0

Value = float | None
Result = tuple[Value, str | None]  # (value, na_reason) — exactly one is set


@dataclass(frozen=True)
class RatioMeta:
    key: str
    display_name: str
    category: str
    formula_display: str
    better_when: str  # higher / lower / depends
    # Display format hint (not in SPEC's yml field list, but needed to render
    # values sanely): percent / x / days / usd / usd_m / raw
    fmt: str = "raw"
    market_data: bool = False  # True = needs a price (Phase 2 on pages)
    caveats: list[str] = field(default_factory=list)


RATIO_META: list[RatioMeta] = [
    # Liquidity
    RatioMeta("current_ratio", "Current Ratio", "Liquidity", "current assets / current liabilities", "higher", "x"),
    RatioMeta("quick_ratio", "Quick Ratio", "Liquidity", "(current assets - inventory) / current liabilities", "higher", "x"),
    RatioMeta("cash_ratio", "Cash Ratio", "Liquidity", "(cash + short-term investments) / current liabilities", "higher", "x"),
    RatioMeta("ocf_ratio", "Operating Cash Flow Ratio", "Liquidity", "cash from operations / current liabilities", "higher", "x"),
    RatioMeta("working_capital", "Working Capital", "Liquidity", "current assets - current liabilities", "depends", "usd_m"),
    # Activity
    RatioMeta("asset_turnover", "Asset Turnover", "Activity", "revenue / average total assets", "higher", "x"),
    RatioMeta("fixed_asset_turnover", "Fixed Asset Turnover", "Activity", "revenue / average net PP&E", "higher", "x"),
    RatioMeta("inventory_turnover", "Inventory Turnover", "Activity", "cost of revenue / average inventory", "higher", "x"),
    RatioMeta("dio", "Days Inventory Outstanding", "Activity", "365 / inventory turnover", "lower", "days"),
    RatioMeta("receivables_turnover", "Receivables Turnover", "Activity", "revenue / average accounts receivable", "higher", "x"),
    RatioMeta("dso", "Days Sales Outstanding", "Activity", "365 / receivables turnover", "lower", "days"),
    RatioMeta("payables_turnover", "Payables Turnover", "Activity", "cost of revenue / average accounts payable", "depends", "x"),
    RatioMeta("dpo", "Days Payables Outstanding", "Activity", "365 / payables turnover", "depends", "days"),
    RatioMeta("ccc", "Cash Conversion Cycle", "Activity", "DIO + DSO - DPO", "lower", "days"),
    # Profitability
    RatioMeta("gross_margin", "Gross Margin", "Profitability", "gross profit / revenue", "higher", "percent"),
    RatioMeta("operating_margin", "Operating Margin", "Profitability", "operating income / revenue", "higher", "percent"),
    RatioMeta("ebitda_margin", "EBITDA Margin", "Profitability", "EBITDA / revenue", "higher", "percent"),
    RatioMeta("pretax_margin", "Pretax Margin", "Profitability", "pretax income / revenue", "higher", "percent"),
    RatioMeta("net_margin", "Net Margin", "Profitability", "net income / revenue", "higher", "percent"),
    RatioMeta("fcf_margin", "FCF Margin", "Profitability", "free cash flow / revenue", "higher", "percent"),
    RatioMeta("roa", "Return on Assets", "Profitability", "net income / average total assets", "higher", "percent"),
    RatioMeta("roe", "Return on Equity", "Profitability", "net income / average equity", "higher", "percent"),
    RatioMeta("roic", "Return on Invested Capital", "Profitability", "NOPAT / average invested capital", "higher", "percent"),
    # DuPont
    RatioMeta("tax_burden", "Tax Burden", "DuPont", "net income / pretax income", "higher", "x"),
    RatioMeta("interest_burden", "Interest Burden", "DuPont", "pretax income / EBIT", "higher", "x"),
    RatioMeta("equity_multiplier", "Equity Multiplier", "DuPont", "average assets / average equity", "depends", "x"),
    # Leverage
    RatioMeta("debt_to_equity", "Debt / Equity", "Leverage", "total debt / total equity", "lower", "x"),
    RatioMeta("debt_to_assets", "Debt / Assets", "Leverage", "total debt / total assets", "lower", "x"),
    RatioMeta("net_debt_to_ebitda", "Net Debt / EBITDA", "Leverage", "net debt / EBITDA", "lower", "x"),
    RatioMeta("interest_coverage", "Interest Coverage", "Leverage", "EBIT / interest expense", "higher", "x"),
    RatioMeta("ebitda_coverage", "EBITDA Coverage", "Leverage", "EBITDA / interest expense", "higher", "x"),
    # Cash Flow
    RatioMeta("capex_to_sales", "Capex / Sales", "Cash Flow", "capex / revenue", "depends", "percent"),
    RatioMeta("capex_to_da", "Capex / D&A", "Cash Flow", "capex / depreciation & amortization", "depends", "x"),
    RatioMeta("accruals_ratio", "Accruals Ratio", "Cash Flow", "(net income - CFO) / average assets", "lower", "percent"),
    RatioMeta("cash_conversion", "Cash Conversion", "Cash Flow", "CFO / net income", "higher", "x"),
    # Shareholder Return (fiscal)
    RatioMeta("payout_ratio", "Payout Ratio", "Shareholder Return", "dividends paid / net income", "depends", "percent"),
    RatioMeta("retention", "Retention Ratio", "Shareholder Return", "1 - payout ratio", "depends", "percent"),
    RatioMeta("sgr", "Sustainable Growth Rate", "Shareholder Return", "ROE x retention", "higher", "percent"),
    RatioMeta("dividend_coverage", "Dividend Coverage", "Shareholder Return", "free cash flow / dividends paid", "higher", "x"),
    # Per Share
    RatioMeta("bvps", "Book Value / Share", "Per Share", "total equity / diluted shares", "higher", "usd"),
    RatioMeta("revenue_per_share", "Revenue / Share", "Per Share", "revenue / diluted shares", "higher", "usd"),
    RatioMeta("fcf_per_share", "FCF / Share", "Per Share", "free cash flow / diluted shares", "higher", "usd"),
    # Growth
    RatioMeta("revenue_yoy", "Revenue Growth YoY", "Growth", "(revenue - prior revenue) / |prior revenue|", "higher", "percent"),
    RatioMeta("ni_yoy", "Net Income Growth YoY", "Growth", "(net income - prior) / |prior|", "higher", "percent"),
    RatioMeta("revenue_cagr_5y", "Revenue CAGR (5y)", "Growth", "(revenue / revenue 4 FYs ago)^(1/4) - 1", "higher", "percent"),
    RatioMeta("rule_of_40", "Rule of 40 (SaaS-oriented)", "Growth", "revenue growth YoY + FCF margin", "higher", "percent",
              caveats=["SaaS-oriented heuristic; not meaningful for most non-software businesses."]),
    # Market-data ratios (Phase 2 on pages; math + yml entries live now)
    RatioMeta("market_cap", "Market Cap", "Valuation-Equity", "price x diluted shares", "depends", "usd_m", market_data=True),
    RatioMeta("pe", "P/E", "Valuation-Equity", "price / diluted EPS", "lower", "x", market_data=True),
    RatioMeta("ps", "P/S", "Valuation-Equity", "market cap / revenue", "lower", "x", market_data=True),
    RatioMeta("pb", "P/B", "Valuation-Equity", "market cap / total equity", "lower", "x", market_data=True),
    RatioMeta("p_fcf", "P/FCF", "Valuation-Equity", "market cap / free cash flow", "lower", "x", market_data=True),
    RatioMeta("earnings_yield", "Earnings Yield", "Valuation-Equity", "diluted EPS / price", "higher", "percent", market_data=True),
    RatioMeta("fcf_yield", "FCF Yield", "Valuation-Equity", "free cash flow / market cap", "higher", "percent", market_data=True),
    RatioMeta("peg", "PEG", "Valuation-Equity", "P/E / (net income growth x 100)", "lower", "x", market_data=True),
    RatioMeta("ev", "Enterprise Value", "Valuation-Enterprise", "market cap + total debt - cash - short-term investments", "depends", "usd_m", market_data=True),
    RatioMeta("ev_ebitda", "EV / EBITDA", "Valuation-Enterprise", "EV / EBITDA", "lower", "x", market_data=True),
    RatioMeta("ev_ebit", "EV / EBIT", "Valuation-Enterprise", "EV / EBIT", "lower", "x", market_data=True),
    RatioMeta("ev_sales", "EV / Sales", "Valuation-Enterprise", "EV / revenue", "lower", "x", market_data=True),
    RatioMeta("ev_fcf", "EV / FCF", "Valuation-Enterprise", "EV / free cash flow", "lower", "x", market_data=True),
    RatioMeta("ev_ic", "EV / Invested Capital", "Valuation-Enterprise", "EV / invested capital", "lower", "x", market_data=True),
    RatioMeta("ev_ebitda_less_capex", "EV / (EBITDA - Capex)", "Valuation-Enterprise", "EV / (EBITDA - capex)", "lower", "x", market_data=True),
    RatioMeta("buyback_yield", "Buyback Yield", "Shareholder Return", "buybacks / market cap", "higher", "percent", market_data=True),
    RatioMeta("shareholder_yield", "Shareholder Yield", "Shareholder Return", "(dividends + buybacks) / market cap", "higher", "percent", market_data=True),
]

RATIO_META_BY_KEY: dict[str, RatioMeta] = {m.key: m for m in RATIO_META}
FISCAL_RATIO_KEYS: list[str] = [m.key for m in RATIO_META if not m.market_data]
CATEGORIES: list[str] = ["Liquidity", "Activity", "Profitability", "DuPont", "Leverage",
                         "Cash Flow", "Valuation-Equity", "Valuation-Enterprise",
                         "Shareholder Return", "Per Share", "Growth"]


def compute_fiscal_ratios(vals: dict[str, dict[int, float]], fy: int) -> dict[str, Result]:
    """All fiscal-data ratios for one company fiscal year.

    vals: canonical_item -> fiscal_year -> value (mapped + derived items).
    Returns key -> (value, na_reason); exactly one side is non-None.
    """
    def g(item: str, year: int | None = None) -> Value:
        return vals.get(item, {}).get(fy if year is None else year)

    out: dict[str, Result] = {}

    def ok(key: str, value: float) -> None:
        out[key] = (value, None)

    def na(key: str, reason: str) -> None:
        out[key] = (None, reason)

    def div(key: str, numer: Value, denom: Value, missing: str,
            zero_reason: str | None = None) -> None:
        """Standard quotient: na on missing input or zero denominator."""
        if numer is None or denom is None:
            na(key, missing)
        elif denom == 0:
            na(key, zero_reason or "zero denominator")
        else:
            ok(key, numer / denom)

    ca, cl = g("current_assets"), g("current_liabilities")
    inv, cash, sti = g("inventory"), g("cash"), g("st_investments")
    cfo, revenue, ni = g("cfo"), g("revenue"), g("net_income")

    # --- Liquidity ---
    div("current_ratio", ca, cl, "missing current assets/liabilities")
    if ca is None or cl is None:
        na("quick_ratio", "missing current assets/liabilities")
    elif cl == 0:
        na("quick_ratio", "zero current liabilities")
    else:
        ok("quick_ratio", (ca - (inv or 0.0)) / cl)
    if cash is None or cl is None:
        na("cash_ratio", "missing cash or current liabilities")
    elif cl == 0:
        na("cash_ratio", "zero current liabilities")
    else:
        ok("cash_ratio", (cash + (sti or 0.0)) / cl)
    div("ocf_ratio", cfo, cl, "missing CFO or current liabilities")
    wc = g("working_capital")
    ok("working_capital", wc) if wc is not None else na("working_capital", "missing current assets/liabilities")

    # --- Activity ---
    div("asset_turnover", revenue, g("avg_assets"), "missing revenue or average assets")
    div("fixed_asset_turnover", revenue, g("avg_ppe"), "missing revenue or average PP&E")
    cor = g("cost_of_revenue")
    avg_inv = g("avg_inventory")
    if avg_inv is None or avg_inv == 0:
        na("inventory_turnover", "no inventory")
        na("dio", "no inventory")
    elif cor is None:
        na("inventory_turnover", "missing cost of revenue")
        na("dio", "missing cost of revenue")
    else:
        turn = cor / avg_inv
        ok("inventory_turnover", turn)
        ok("dio", DAYS_PER_YEAR / turn) if turn != 0 else na("dio", "zero inventory turnover")
    div("receivables_turnover", revenue, g("avg_ar"), "missing revenue or average receivables")
    rt = out["receivables_turnover"][0]
    div("dso", DAYS_PER_YEAR if rt is not None else None, rt, out["receivables_turnover"][1] or "missing receivables turnover")
    div("payables_turnover", cor, g("avg_ap"), "missing cost of revenue or average payables")
    pt = out["payables_turnover"][0]
    div("dpo", DAYS_PER_YEAR if pt is not None else None, pt, out["payables_turnover"][1] or "missing payables turnover")
    dio_v, dso_v, dpo_v = out["dio"][0], out["dso"][0], out["dpo"][0]
    if None in (dio_v, dso_v, dpo_v):
        first_reason = next(r for v, r in (out["dio"], out["dso"], out["dpo"]) if v is None)
        na("ccc", first_reason)
    else:
        ok("ccc", dio_v + dso_v - dpo_v)

    # --- Profitability ---
    div("gross_margin", g("gross_profit"), revenue, "missing gross profit or revenue")
    div("operating_margin", g("operating_income"), revenue, "missing operating income or revenue")
    div("ebitda_margin", g("ebitda"), revenue, "missing EBITDA (operating income or D&A unmapped)")
    div("pretax_margin", g("pretax_income"), revenue, "missing pretax income or revenue")
    div("net_margin", ni, revenue, "missing net income or revenue")
    fcf = g("fcf")
    div("fcf_margin", fcf, revenue, "missing FCF (CFO or capex unmapped)")
    div("roa", ni, g("avg_assets"), "missing net income or average assets")
    avg_eq = g("avg_equity")
    if ni is None or avg_eq is None:
        na("roe", "missing net income or average equity")
    elif avg_eq <= 0:
        na("roe", "non-positive average equity")
    else:
        ok("roe", ni / avg_eq)
    nopat, avg_ic = g("nopat"), g("avg_ic")
    if nopat is None:
        na("roic", "NOPAT unavailable (pretax income <= 0 or inputs unmapped)")
    elif avg_ic is None:
        na("roic", "missing average invested capital")
    elif avg_ic <= 0:
        na("roic", "non-positive average invested capital")
    else:
        ok("roic", nopat / avg_ic)

    # --- DuPont ---
    div("tax_burden", ni, g("pretax_income"), "missing net income or pretax income")
    ebit = g("ebit")
    div("interest_burden", g("pretax_income"), ebit, "missing pretax income or EBIT")
    avg_assets = g("avg_assets")
    if avg_assets is None or avg_eq is None:
        na("equity_multiplier", "missing average assets or equity")
    elif avg_eq <= 0:
        na("equity_multiplier", "non-positive average equity")
    else:
        ok("equity_multiplier", avg_assets / avg_eq)

    # --- Leverage ---
    total_debt, equity = g("total_debt"), g("total_equity")
    if total_debt is None or equity is None:
        na("debt_to_equity", "missing total debt or equity")
    elif equity <= 0:
        na("debt_to_equity", "non-positive equity")
    else:
        ok("debt_to_equity", total_debt / equity)
    div("debt_to_assets", total_debt, g("total_assets"), "missing total debt or assets")
    net_debt, ebitda = g("net_debt"), g("ebitda")
    if net_debt is None or ebitda is None:
        na("net_debt_to_ebitda", "missing net debt or EBITDA")
    elif ebitda <= 0:
        na("net_debt_to_ebitda", "non-positive EBITDA")
    else:
        ok("net_debt_to_ebitda", net_debt / ebitda)
    interest = g("interest_expense")
    if interest is None or interest == 0:
        na("interest_coverage", "no interest expense")
        na("ebitda_coverage", "no interest expense")
    else:
        div("interest_coverage", ebit, interest, "missing EBIT")
        div("ebitda_coverage", ebitda, interest, "missing EBITDA")

    # --- Cash Flow ---
    div("capex_to_sales", g("capex"), revenue, "missing capex or revenue")
    div("capex_to_da", g("capex"), g("d_and_a"), "missing capex or D&A")
    if ni is None or cfo is None or avg_assets is None:
        na("accruals_ratio", "missing net income, CFO, or average assets")
    elif avg_assets == 0:
        na("accruals_ratio", "zero average assets")
    else:
        ok("accruals_ratio", (ni - cfo) / avg_assets)
    div("cash_conversion", cfo, ni, "missing CFO or net income", zero_reason="zero net income")

    # --- Shareholder Return ---
    # A missing dividends_paid tag is treated as "paid no dividends" — that is
    # what it means for nearly every company that has never declared one.
    dividends = g("dividends_paid") or 0.0
    if ni is None or ni <= 0:
        na("payout_ratio", "non-positive net income")
        na("retention", "non-positive net income")
    else:
        ok("payout_ratio", dividends / ni)
        ok("retention", 1 - dividends / ni)
    roe_v, ret_v = out["roe"][0], out["retention"][0]
    if roe_v is None or ret_v is None:
        na("sgr", out["roe"][1] or out["retention"][1])
    else:
        ok("sgr", roe_v * ret_v)
    if dividends == 0:
        na("dividend_coverage", "no dividends paid")
    else:
        div("dividend_coverage", fcf, dividends, "missing FCF (CFO or capex unmapped)")

    # --- Per Share ---
    shares = g("shares_diluted")
    div("bvps", equity, shares, "missing equity or diluted shares", zero_reason="zero diluted shares")
    div("revenue_per_share", revenue, shares, "missing revenue or diluted shares", zero_reason="zero diluted shares")
    div("fcf_per_share", fcf, shares, "missing FCF or diluted shares", zero_reason="zero diluted shares")

    # --- Growth ---
    out["revenue_yoy"] = _yoy(revenue, g("revenue", fy - 1), "revenue")
    out["ni_yoy"] = _yoy(ni, g("net_income", fy - 1), "net income")
    rev_old = g("revenue", fy - 4)
    if revenue is None or rev_old is None:
        na("revenue_cagr_5y", "missing revenue 4 fiscal years apart")
    elif revenue <= 0 or rev_old <= 0:
        na("revenue_cagr_5y", "requires positive revenue at both endpoints")
    else:
        ok("revenue_cagr_5y", (revenue / rev_old) ** 0.25 - 1)
    rev_yoy_v, fcf_m = out["revenue_yoy"][0], out["fcf_margin"][0]
    if rev_yoy_v is None or fcf_m is None:
        na("rule_of_40", out["revenue_yoy"][1] or out["fcf_margin"][1])
    else:
        ok("rule_of_40", rev_yoy_v + fcf_m)

    return out


def _yoy(current: Value, prior: Value, label: str) -> Result:
    if current is None or prior is None:
        return (None, f"missing prior-year {label}")
    if prior == 0:
        return (None, f"zero prior-year {label}")
    return ((current - prior) / abs(prior), None)


def compute_market_ratios(price: float, vals: dict[str, Value]) -> dict[str, Result]:
    """Market-data ratios from a price + latest-FY fundamentals (SPEC 10.2).
    Pure function — Phase 2 wires it to live quotes; tests stub the price.
    vals holds latest-FY values for the items named below."""
    out: dict[str, Result] = {}

    def ok(key: str, value: float) -> None:
        out[key] = (value, None)

    def na(key: str, reason: str) -> None:
        out[key] = (None, reason)

    def multiple(key: str, numer: Value, denom: Value, what: str) -> None:
        """EV-style multiple: non-positive denominator -> n/a per SPEC."""
        if numer is None or denom is None:
            na(key, f"missing {what}")
        elif denom <= 0:
            na(key, "non-positive denominator")
        else:
            ok(key, numer / denom)

    shares = vals.get("shares_diluted")
    if shares is None or shares <= 0:
        for key in [m.key for m in RATIO_META if m.market_data]:
            na(key, "missing diluted shares")
        return out
    mcap = price * shares
    ok("market_cap", mcap)

    total_debt = vals.get("total_debt") or 0.0
    cash = vals.get("cash") or 0.0
    sti = vals.get("st_investments") or 0.0
    ev = mcap + total_debt - cash - sti
    ok("ev", ev)

    eps = vals.get("eps_diluted")
    multiple("pe", price, eps, "diluted EPS")
    multiple("ps", mcap, vals.get("revenue"), "revenue")
    multiple("pb", mcap, vals.get("total_equity"), "total equity")
    multiple("p_fcf", mcap, vals.get("fcf"), "FCF")
    if eps is None:
        na("earnings_yield", "missing diluted EPS")
    else:
        ok("earnings_yield", eps / price)
    fcf = vals.get("fcf")
    if fcf is None:
        na("fcf_yield", "missing FCF")
    else:
        ok("fcf_yield", fcf / mcap)
    multiple("ev_ebitda", ev, vals.get("ebitda"), "EBITDA")
    multiple("ev_ebit", ev, vals.get("ebit"), "EBIT")
    multiple("ev_sales", ev, vals.get("revenue"), "revenue")
    multiple("ev_fcf", ev, vals.get("fcf"), "FCF")
    multiple("ev_ic", ev, vals.get("invested_capital"), "invested capital")
    ebitda, capex = vals.get("ebitda"), vals.get("capex")
    if ebitda is None or capex is None:
        na("ev_ebitda_less_capex", "missing EBITDA or capex")
    elif ebitda - capex <= 0:
        na("ev_ebitda_less_capex", "non-positive denominator")
    else:
        ok("ev_ebitda_less_capex", ev / (ebitda - capex))
    buybacks = vals.get("buybacks") or 0.0
    dividends = vals.get("dividends_paid") or 0.0
    ok("buyback_yield", buybacks / mcap)
    ok("shareholder_yield", (dividends + buybacks) / mcap)
    pe = out["pe"][0]
    ni_yoy = vals.get("ni_yoy")
    if pe is None or ni_yoy is None or ni_yoy <= 0:
        na("peg", "requires positive net income growth")
    else:
        ok("peg", pe / (ni_yoy * 100))
    return out


def recompute_company(session: Session, cik: str) -> int:
    """Rebuild all fiscal-data ratio rows for a company from its facts."""
    vals: dict[str, dict[int, float]] = {}
    for fact in session.execute(
        select(StatementFact).where(StatementFact.cik == cik)
    ).scalars():
        if fact.value is not None:
            vals.setdefault(fact.canonical_item, {})[fact.fiscal_year] = fact.value
    if not vals:
        session.execute(delete(Ratio).where(Ratio.cik == cik))
        session.commit()
        return 0

    max_fy = max(fy for years in vals.values() for fy in years)
    display_years = list(range(max_fy, max_fy - 5, -1))
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)

    session.execute(delete(Ratio).where(Ratio.cik == cik))
    count = 0
    for fy in display_years:
        results = compute_fiscal_ratios(vals, fy)
        for key in FISCAL_RATIO_KEYS:
            value, reason = results.get(key, (None, "not computed"))
            session.add(Ratio(cik=cik, fiscal_year=fy, ratio_key=key,
                              value=value, na_reason=reason, computed_at=now))
            count += 1
    session.commit()
    return count
