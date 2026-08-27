"""Canonical line items, XBRL tag fallback chains, and companyfacts parsing.

SPEC 10.1 rules implemented here:
- us-gaap facts only; USD for money, shares for share counts, USD/shares for EPS.
- Annual values only: form == "10-K" and fp == "FY".
- Duration facts (IS/CF) must span 330-400 days to exclude quarterly stubs.
- Restatements: same (item, fiscal_year) in multiple filings -> most recently
  filed value wins.
- Fallback chains: per item AND per fiscal year, the first tag in the chain
  with a value for that year is used, and xbrl_tag_used records it.

One non-obvious mechanic, verified against real companyfacts data: the `fy`
field on a fact labels the REPORT the fact appeared in, not the fact's own
period. A FY2026 10-K reports FY2026, FY2025, and FY2024 comparatives, and
all three facts carry fy=2026. So fiscal years are assigned like this:
  1. For each 10-K accession, find its own period end (the latest annual
     period end among that accession's facts) and pair it with the
     accession's fy label. That gives a calendar of period_end -> fiscal_year.
  2. Every fact (comparatives included) then gets its fiscal year by exact
     period-end lookup in that calendar. Comparative period ends are byte-
     identical across filings, so this is reliable even for 52/53-week
     fiscal calendars where the year-end date drifts.
This is what makes the restatement rule implementable: restated comparatives
from a newer 10-K land on the right fiscal year and win on filed date.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# 5 fiscal years are displayed; one extra prior year is stored so that
# average-balance denominators (avg_assets etc.) for the oldest displayed
# year are true two-point averages.
DISPLAY_YEARS = 5
STORE_YEARS = DISPLAY_YEARS + 1

MIN_ANNUAL_DAYS = 330
MAX_ANNUAL_DAYS = 400

# (canonical_item, [tag fallback chain]) in SPEC 10.1 display order.
INCOME_STATEMENT_ITEMS: list[tuple[str, list[str]]] = [
    # Two tags appended beyond the SPEC chain, both placed last so they only
    # apply when nothing standard matched:
    #   RevenuesNetOfInterestExpense — how investment banks state the top line
    #     (Goldman, Morgan Stanley); without it their revenue row, and every
    #     margin and multiple built on it, is empty.
    #   RegulatedAndUnregulatedOperatingRevenue — the utilities' top line
    #     (DTE, Xcel).
    # Deliberately NOT added: InterestAndDividendIncomeOperating. Commercial
    # banks tag gross interest income with it, which is not comparable to
    # revenue anywhere else in the table — an honest "n/a" beats a number
    # that would silently wreck every margin comparison.
    ("revenue", ["RevenueFromContractWithCustomerExcludingAssessedTax",
                 "RevenueFromContractWithCustomerIncludingAssessedTax",
                 "Revenues", "SalesRevenueNet", "RevenuesNetOfInterestExpense",
                 "RegulatedAndUnregulatedOperatingRevenue"]),
    ("cost_of_revenue", ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"]),
    ("gross_profit", ["GrossProfit"]),  # falls back to revenue - cost_of_revenue, see below
    ("rd_expense", ["ResearchAndDevelopmentExpense"]),
    ("sga_expense", ["SellingGeneralAndAdministrativeExpense", "GeneralAndAdministrativeExpense"]),
    ("operating_income", ["OperatingIncomeLoss"]),
    ("interest_expense", ["InterestExpense", "InterestExpenseNonoperating", "InterestIncomeExpenseNet"]),
    ("pretax_income", ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                       "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"]),
    ("income_tax_expense", ["IncomeTaxExpenseBenefit"]),
    ("net_income", ["NetIncomeLoss"]),
    ("eps_diluted", ["EarningsPerShareDiluted"]),
    ("shares_diluted", ["WeightedAverageNumberOfDilutedSharesOutstanding"]),
]

BALANCE_SHEET_ITEMS: list[tuple[str, list[str]]] = [
    ("cash", ["CashAndCashEquivalentsAtCarryingValue"]),
    ("st_investments", ["ShortTermInvestments", "MarketableSecuritiesCurrent",
                        "AvailableForSaleSecuritiesDebtSecuritiesCurrent"]),
    ("accounts_receivable", ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"]),
    ("inventory", ["InventoryNet"]),
    ("current_assets", ["AssetsCurrent"]),
    ("ppe_net", ["PropertyPlantAndEquipmentNet"]),
    ("goodwill", ["Goodwill"]),
    ("intangibles", ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet"]),
    ("total_assets", ["Assets"]),
    ("accounts_payable", ["AccountsPayableCurrent", "AccountsPayableAndAccruedLiabilitiesCurrent"]),
    ("deferred_revenue_current", ["ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent"]),
    ("short_term_debt", ["DebtCurrent", "LongTermDebtCurrent", "NotesPayableCurrent",
                         "ShortTermBorrowings"]),  # special combine rule, see below
    ("current_liabilities", ["LiabilitiesCurrent"]),
    # LongTermNotesPayable appended beyond the SPEC chain: Oracle (and others
    # that label the line "notes payable, non-current") report it instead of
    # LongTermDebtNoncurrent; without it total_debt silently loses ~$90B+.
    ("long_term_debt", ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermNotesPayable",
                        "LongTermDebtAndCapitalLeaseObligations"]),
    ("total_liabilities", ["Liabilities"]),
    ("total_equity", ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                      "StockholdersEquity"]),
]

CASH_FLOW_ITEMS: list[tuple[str, list[str]]] = [
    ("cfo", ["NetCashProvidedByUsedInOperatingActivities",
             "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]),
    ("d_and_a", ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
                 "DepreciationAndAmortization"]),
    ("stock_comp", ["ShareBasedCompensation"]),
    ("capex", ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]),
    ("cfi", ["NetCashProvidedByUsedInInvestingActivities"]),
    ("dividends_paid", ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"]),
    ("buybacks", ["PaymentsForRepurchaseOfCommonStock"]),
    # Senior/plain variants appended beyond the SPEC chains (Oracle uses them).
    ("debt_issued", ["ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromIssuanceOfSeniorLongTermDebt"]),
    ("debt_repaid", ["RepaymentsOfLongTermDebt", "RepaymentsOfDebt"]),
    ("cff", ["NetCashProvidedByUsedInFinancingActivities"]),
]

STATEMENTS: list[tuple[str, list[tuple[str, list[str]]]]] = [
    ("IS", INCOME_STATEMENT_ITEMS),
    ("BS", BALANCE_SHEET_ITEMS),
    ("CF", CASH_FLOW_ITEMS),
]

# Units per item; default is USD.
ITEM_UNITS: dict[str, str] = {
    "eps_diluted": "USD/shares",
    "shares_diluted": "shares",
}

# Human labels for statement rows (canonical item -> display text).
ITEM_LABELS: dict[str, str] = {
    "revenue": "Revenue", "cost_of_revenue": "Cost of revenue",
    "gross_profit": "Gross profit", "rd_expense": "R&D expense",
    "sga_expense": "SG&A expense", "operating_income": "Operating income",
    "interest_expense": "Interest expense", "pretax_income": "Pretax income",
    "income_tax_expense": "Income tax expense", "net_income": "Net income",
    "eps_diluted": "Diluted EPS", "shares_diluted": "Diluted shares",
    "cash": "Cash & equivalents", "st_investments": "Short-term investments",
    "accounts_receivable": "Accounts receivable", "inventory": "Inventory",
    "current_assets": "Total current assets", "ppe_net": "PP&E, net",
    "goodwill": "Goodwill", "intangibles": "Intangibles, net",
    "total_assets": "Total assets", "accounts_payable": "Accounts payable",
    "deferred_revenue_current": "Deferred revenue (current)",
    "short_term_debt": "Short-term debt", "current_liabilities": "Total current liabilities",
    "long_term_debt": "Long-term debt", "total_liabilities": "Total liabilities",
    "total_equity": "Total equity",
    "cfo": "Cash from operations", "d_and_a": "Depreciation & amortization",
    "stock_comp": "Stock-based compensation", "capex": "Capital expenditures",
    "cfi": "Cash from investing", "dividends_paid": "Dividends paid",
    "buybacks": "Share repurchases", "debt_issued": "Debt issued",
    "debt_repaid": "Debt repaid", "cff": "Cash from financing",
}

STATEMENT_NAMES = {"IS": "Income Statement", "BS": "Balance Sheet", "CF": "Cash Flow Statement"}

# Duration (flow) statements vs instant (balance) facts.
DURATION_STATEMENTS = {"IS", "CF"}

# Items used for the coverage acceptance metric ("< 10% missing on core
# items"). Deliberately excludes items many industries legitimately lack
# (inventory, cost_of_revenue for banks, ...).
CORE_ITEMS = ["revenue", "operating_income", "net_income", "total_assets",
              "total_equity", "cfo", "capex"]

# Near-universal tags used to anchor each 10-K accession's own period end.
# (Anchoring on all tags would risk picking up post-period subsequent-event
# facts; these tags always describe the report's own periods.)
_ANCHOR_TAGS = [
    "Assets", "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "LiabilitiesAndStockholdersEquity", "NetIncomeLoss", "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "OperatingIncomeLoss", "CashAndCashEquivalentsAtCarryingValue",
]


@dataclass(frozen=True)
class MappedFact:
    statement: str
    item: str
    fiscal_year: int
    period_end: dt.date
    value: float
    unit: str
    tag: str
    form: str
    filed: dt.date


@dataclass
class ParseResult:
    facts: list[MappedFact]
    # Items with no value in any of the DISPLAY_YEARS newest fiscal years.
    missing_items: list[str]
    fiscal_years: list[int]  # stored years, newest first


def _parse_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def _is_annual_duration(fact: dict) -> bool:
    start = _parse_date(fact.get("start"))
    end = _parse_date(fact.get("end"))
    if start is None or end is None:
        return False
    return MIN_ANNUAL_DAYS <= (end - start).days <= MAX_ANNUAL_DAYS


def _annual_facts(tag_data: dict, unit: str, duration: bool):
    """Yield 10-K/FY facts of the right unit (and annual span, for flows)."""
    for fact in tag_data.get("units", {}).get(unit, []):
        if fact.get("form") != "10-K" or fact.get("fp") != "FY":
            continue
        if fact.get("val") is None or not fact.get("end"):
            continue
        if duration:
            if not _is_annual_duration(fact):
                continue
        elif fact.get("start"):
            continue  # instant expected; skip stray duration facts
        yield fact


def build_fy_calendar(gaap: dict) -> dict[dt.date, int]:
    """Map each 10-K's own period end date -> its fy label (see module doc)."""
    # accession -> (fy, filed, latest anchor end seen)
    per_accession: dict[str, tuple[int, dt.date, dt.date]] = {}
    for tag in _ANCHOR_TAGS:
        tag_data = gaap.get(tag)
        if not tag_data:
            continue
        duration = "Income" in tag or "Revenue" in tag  # crude but only anchors need it
        for fact in _annual_facts(tag_data, "USD", duration=duration):
            fy, accn = fact.get("fy"), fact.get("accn")
            end, filed = _parse_date(fact.get("end")), _parse_date(fact.get("filed"))
            if fy is None or accn is None or end is None or filed is None:
                continue
            current = per_accession.get(accn)
            if current is None or end > current[2]:
                per_accession[accn] = (int(fy), filed, end)

    calendar: dict[dt.date, int] = {}
    latest_filed: dict[dt.date, dt.date] = {}
    for fy, filed, end in per_accession.values():
        if end not in calendar or filed > latest_filed[end]:
            calendar[end] = fy
            latest_filed[end] = filed
    return calendar


def _collect_tag(gaap: dict, tag: str, unit: str, duration: bool,
                 calendar: dict[dt.date, int]) -> dict[int, dict]:
    """fy -> winning fact dict for one tag (latest filed wins = restatements)."""
    tag_data = gaap.get(tag)
    if not tag_data:
        return {}
    best: dict[int, dict] = {}
    for fact in _annual_facts(tag_data, unit, duration):
        end = _parse_date(fact.get("end"))
        filed = _parse_date(fact.get("filed"))
        if end is None or filed is None:
            continue
        fy = calendar.get(end)
        if fy is None:
            continue  # period end not anchored to any 10-K's own year; skip
        current = best.get(fy)
        if current is None or filed > _parse_date(current.get("filed")):
            best[fy] = fact
    return best


def parse_companyfacts(facts_json: dict) -> ParseResult:
    """Map raw companyfacts JSON to canonical items for the stored years."""
    gaap = facts_json.get("facts", {}).get("us-gaap", {})
    calendar = build_fy_calendar(gaap)
    if not calendar:
        return ParseResult(facts=[], missing_items=[i for _, items in STATEMENTS for i, _ in items],
                           fiscal_years=[])

    max_fy = max(calendar.values())
    stored_years = [fy for fy in range(max_fy, max_fy - STORE_YEARS, -1)]
    display_years = set(stored_years[:DISPLAY_YEARS])

    # item -> fy -> (fact dict, tag used)
    selected: dict[str, dict[int, tuple[dict, str]]] = {}
    statements_by_item: dict[str, str] = {}

    for statement, items in STATEMENTS:
        duration = statement in DURATION_STATEMENTS
        for item, chain in items:
            statements_by_item[item] = statement
            unit = ITEM_UNITS.get(item, "USD")
            per_tag = {tag: _collect_tag(gaap, tag, unit, duration, calendar) for tag in chain}
            chosen: dict[int, tuple[dict, str]] = {}
            for fy in stored_years:
                if item == "short_term_debt":
                    picked = _pick_short_term_debt(per_tag, fy)
                else:
                    picked = _first_in_chain(per_tag, chain, fy)
                if picked is not None:
                    chosen[fy] = picked
            selected[item] = chosen

    _apply_gross_profit_fallback(selected, stored_years)
    _apply_computed_fallbacks(gaap, calendar, selected, stored_years)

    facts: list[MappedFact] = []
    missing: list[str] = []
    for item, chosen in selected.items():
        statement = statements_by_item[item]
        unit = ITEM_UNITS.get(item, "USD")
        if not any(fy in display_years for fy in chosen):
            missing.append(item)
        for fy, (fact, tag) in chosen.items():
            facts.append(MappedFact(
                statement=statement,
                item=item,
                fiscal_year=fy,
                period_end=_parse_date(fact.get("end")),
                value=float(fact["val"]),
                unit=unit,
                tag=tag,
                form=fact.get("form", "10-K"),
                filed=_parse_date(fact.get("filed")),
            ))
    return ParseResult(facts=facts, missing_items=sorted(missing), fiscal_years=stored_years)


def _first_in_chain(per_tag: dict[str, dict[int, dict]], chain: list[str],
                    fy: int) -> tuple[dict, str] | None:
    """First tag in the chain with a value for this year — preferring the
    first NON-ZERO value, then falling back to a zero if that's all there is.

    Why: some filers leave a stray 0-valued fact on a high-priority tag while
    the real balance sits on a later tag (seen in the wild: Oracle's FY2022
    10-K tags LongTermDebt=0 next to LongTermNotesPayable=$72.1B). A genuine
    zero is still kept when no tag in the chain has a non-zero value."""
    fallback: tuple[dict, str] | None = None
    for tag in chain:
        fact = per_tag.get(tag, {}).get(fy)
        if fact is None:
            continue
        if float(fact["val"]) != 0.0:
            return (fact, tag)
        if fallback is None:
            fallback = (fact, tag)
    return fallback


def _pick_short_term_debt(per_tag: dict[str, dict[int, dict]], fy: int) -> tuple[dict, str] | None:
    """SPEC rule: DebtCurrent first; when absent and BOTH LongTermDebtCurrent
    and ShortTermBorrowings exist, sum them; otherwise fall through the chain
    (with the same non-zero preference as _first_in_chain)."""
    debt_current = per_tag.get("DebtCurrent", {}).get(fy)
    if debt_current is not None and float(debt_current["val"]) != 0.0:
        return (debt_current, "DebtCurrent")
    ltdc = per_tag.get("LongTermDebtCurrent", {}).get(fy)
    stb = per_tag.get("ShortTermBorrowings", {}).get(fy)
    if ltdc is not None and stb is not None:
        combined = dict(ltdc)
        combined["val"] = float(ltdc["val"]) + float(stb["val"])
        # keep the later filed date of the two for the tooltip
        if _parse_date(stb.get("filed")) > _parse_date(ltdc.get("filed")):
            combined["filed"] = stb.get("filed")
        return (combined, "LongTermDebtCurrent+ShortTermBorrowings")
    picked = _first_in_chain(
        per_tag, ["LongTermDebtCurrent", "NotesPayableCurrent", "ShortTermBorrowings"], fy
    )
    if picked is not None:
        return picked
    return (debt_current, "DebtCurrent") if debt_current is not None else None


def _apply_computed_fallbacks(gaap: dict, calendar: dict[dt.date, int],
                              selected: dict[str, dict[int, tuple[dict, str]]],
                              stored_years: list[int]) -> None:
    """Computed fallbacks beyond the SPEC tag chains, applied only to years
    the chains left empty (flagged as a spec extension; see coverage report):

    - pretax_income: some filers (Oracle among them) stop tagging the total
      and only tag the Domestic + Foreign components — sum them.
    - d_and_a: some filers split Depreciation and AmortizationOfIntangible-
      Assets into separate cash-flow lines — sum them (amortization counted
      as 0 when the filer reports none).
    """
    pretax = selected.setdefault("pretax_income", {})
    domestic = _collect_tag(gaap, "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
                            "USD", True, calendar)
    foreign = _collect_tag(gaap, "IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign",
                           "USD", True, calendar)
    for fy in stored_years:
        if fy in pretax or fy not in domestic or fy not in foreign:
            continue
        fact = dict(domestic[fy])
        fact["val"] = float(domestic[fy]["val"]) + float(foreign[fy]["val"])
        pretax[fy] = (fact, "computed:PretaxDomestic+PretaxForeign")

    dna = selected.setdefault("d_and_a", {})
    depreciation = _collect_tag(gaap, "Depreciation", "USD", True, calendar)
    amortization = _collect_tag(gaap, "AmortizationOfIntangibleAssets", "USD", True, calendar)
    for fy in stored_years:
        if fy in dna or fy not in depreciation:
            continue
        fact = dict(depreciation[fy])
        amort = float(amortization[fy]["val"]) if fy in amortization else 0.0
        fact["val"] = float(depreciation[fy]["val"]) + amort
        dna[fy] = (fact, "computed:Depreciation+AmortizationOfIntangibleAssets")

    # total_liabilities = total_assets - total_equity (accounting identity;
    # equity incl. noncontrolling interests). Some filers (Oracle) never tag
    # the Liabilities total.
    liabilities = selected.setdefault("total_liabilities", {})
    for fy in stored_years:
        if fy in liabilities:
            continue
        assets = selected.get("total_assets", {}).get(fy)
        equity = selected.get("total_equity", {}).get(fy)
        if assets is None or equity is None:
            continue
        fact = dict(assets[0])
        fact["val"] = float(assets[0]["val"]) - float(equity[0]["val"])
        liabilities[fy] = (fact, "computed:total_assets-total_equity")


def _apply_gross_profit_fallback(selected: dict[str, dict[int, tuple[dict, str]]],
                                 stored_years: list[int]) -> None:
    """gross_profit = revenue - cost_of_revenue for years missing GrossProfit."""
    gp = selected.setdefault("gross_profit", {})
    for fy in stored_years:
        if fy in gp:
            continue
        rev = selected.get("revenue", {}).get(fy)
        cor = selected.get("cost_of_revenue", {}).get(fy)
        if rev is None or cor is None:
            continue
        fact = dict(rev[0])
        fact["val"] = float(rev[0]["val"]) - float(cor[0]["val"])
        gp[fy] = (fact, "computed:revenue-cost_of_revenue")
