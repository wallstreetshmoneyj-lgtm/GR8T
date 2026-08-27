"""Derived-item computation and storage (SPEC 10.1).

These pin the missing-component conventions documented at the top of
pipelines/statements.py, because they decide whether a ratio shows a number
or an n/a for hundreds of companies.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from core.db import Ratio, StatementFact
from pipelines import statements
from pipelines.statements import build_values
from pipelines.xbrl_map import MappedFact, ParseResult, parse_companyfacts


def make_result(years: list[int], items: dict[str, dict[int, float]]) -> ParseResult:
    facts = [
        MappedFact(statement="IS", item=item, fiscal_year=fy, period_end=dt.date(fy, 12, 31),
                   value=value, unit="USD", tag="Tag", form="10-K",
                   filed=dt.date(fy + 1, 2, 1))
        for item, by_year in items.items() for fy, value in by_year.items()
    ]
    return ParseResult(facts=facts, missing_items=[], fiscal_years=years)


class TestDerivedItems:
    def test_ebitda_is_operating_income_plus_da(self):
        vals = build_values(make_result([2026], {
            "operating_income": {2026: 100.0}, "d_and_a": {2026: 25.0}}))
        assert vals["ebitda"][2026] == 125.0
        assert vals["ebit"][2026] == 100.0

    def test_ebitda_is_absent_when_da_is_unmapped(self):
        vals = build_values(make_result([2026], {"operating_income": {2026: 100.0}}))
        assert 2026 not in vals.get("ebitda", {})

    def test_ebit_falls_back_to_pretax_plus_interest(self):
        # ~21% of the S&P 500 (IBM among them) never tag OperatingIncomeLoss.
        vals = build_values(make_result([2026], {
            "pretax_income": {2026: 900.0}, "interest_expense": {2026: 100.0}}))
        assert vals["ebit"][2026] == 1000.0

    def test_reported_operating_income_wins_over_the_fallback(self):
        vals = build_values(make_result([2026], {
            "operating_income": {2026: 1000.0},
            "pretax_income": {2026: 500.0}, "interest_expense": {2026: 50.0}}))
        assert vals["ebit"][2026] == 1000.0

    def test_ebit_fallback_does_not_invent_an_operating_income_row(self):
        """The derived analytic item is filled; the income statement line the
        company never reported stays empty."""
        vals = build_values(make_result([2026], {
            "pretax_income": {2026: 900.0}, "interest_expense": {2026: 100.0}}))
        assert vals["ebit"][2026] == 1000.0
        assert 2026 not in vals.get("operating_income", {})

    def test_ebit_is_absent_when_neither_source_is_available(self):
        vals = build_values(make_result([2026], {"pretax_income": {2026: 900.0}}))
        assert 2026 not in vals.get("ebit", {})

    def test_total_debt_treats_one_missing_side_as_zero(self):
        # Companies with no short-term debt simply don't report the tag.
        vals = build_values(make_result([2026], {"long_term_debt": {2026: 500.0}}))
        assert vals["total_debt"][2026] == 500.0

    def test_total_debt_is_absent_when_both_sides_are_unmapped(self):
        vals = build_values(make_result([2026], {"cash": {2026: 10.0}}))
        assert 2026 not in vals.get("total_debt", {})

    def test_net_debt_nets_cash_and_short_term_investments(self):
        vals = build_values(make_result([2026], {
            "short_term_debt": {2026: 100.0}, "long_term_debt": {2026: 400.0},
            "cash": {2026: 200.0}, "st_investments": {2026: 50.0}}))
        assert vals["net_debt"][2026] == 250.0  # 500 - 200 - 50

    def test_effective_tax_rate_and_nopat(self):
        vals = build_values(make_result([2026], {
            "operating_income": {2026: 1000.0}, "income_tax_expense": {2026: 200.0},
            "pretax_income": {2026: 800.0}}))
        assert vals["effective_tax_rate"][2026] == pytest.approx(0.25)
        assert vals["nopat"][2026] == pytest.approx(750.0)  # 1000 x (1 - 0.25)

    def test_nopat_is_absent_when_pretax_is_non_positive(self):
        # SPEC 10.1: effective tax rate is null when pretax <= 0, so NOPAT is too.
        vals = build_values(make_result([2026], {
            "operating_income": {2026: 1000.0}, "income_tax_expense": {2026: 50.0},
            "pretax_income": {2026: -300.0}}))
        assert 2026 not in vals.get("nopat", {})

    def test_fcf_requires_both_cfo_and_capex(self):
        with_both = build_values(make_result([2026], {
            "cfo": {2026: 100.0}, "capex": {2026: 30.0}}))
        assert with_both["fcf"][2026] == 70.0
        # A missing capex means the filer reports none (banks) — not "FCF == CFO".
        cfo_only = build_values(make_result([2026], {"cfo": {2026: 100.0}}))
        assert 2026 not in cfo_only.get("fcf", {})

    def test_working_capital(self):
        vals = build_values(make_result([2026], {
            "current_assets": {2026: 500.0}, "current_liabilities": {2026: 300.0}}))
        assert vals["working_capital"][2026] == 200.0

    def test_invested_capital_requires_equity(self):
        vals = build_values(make_result([2026], {
            "long_term_debt": {2026: 500.0}, "total_equity": {2026: 1000.0},
            "cash": {2026: 100.0}, "st_investments": {2026: 50.0}}))
        assert vals["invested_capital"][2026] == 1350.0  # 500 + 1000 - 100 - 50


class TestAverages:
    def test_average_uses_current_and_prior_year(self):
        vals = build_values(make_result([2026, 2025], {
            "total_assets": {2026: 1200.0, 2025: 800.0}}))
        assert vals["avg_assets"][2026] == 1000.0

    def test_average_falls_back_to_the_current_year_when_prior_is_missing(self):
        vals = build_values(make_result([2026], {"total_assets": {2026: 1200.0}}))
        assert vals["avg_assets"][2026] == 1200.0

    def test_avg_ppe_exists_for_fixed_asset_turnover(self):
        # SPEC 10.2 uses "avg ppe" though 10.1's averages list omits it.
        vals = build_values(make_result([2026, 2025], {
            "ppe_net": {2026: 200.0, 2025: 100.0}}))
        assert vals["avg_ppe"][2026] == 150.0

    def test_oldest_displayed_year_gets_a_true_two_point_average(self, orcl_facts):
        """The extra stored year exists so FY-4's averages aren't one-point."""
        result = parse_companyfacts(orcl_facts)
        vals = build_values(result)
        oldest_displayed = result.fiscal_years[4]
        assets = vals["total_assets"]
        expected = (assets[oldest_displayed] + assets[oldest_displayed - 1]) / 2
        assert vals["avg_assets"][oldest_displayed] == pytest.approx(expected)


class TestStorage:
    def test_refresh_stores_mapped_and_derived_facts(self, db, orcl_company, orcl_facts):
        with db() as session:
            statements.refresh_company(session, orcl_company, facts_json=orcl_facts)
            rows = list(session.execute(select(StatementFact)).scalars())

        by_statement = {r.statement for r in rows}
        assert {"IS", "BS", "CF", "DERIVED"} <= by_statement
        derived = {r.canonical_item for r in rows if r.statement == "DERIVED"}
        assert {"ebitda", "fcf", "total_debt", "avg_equity", "avg_ic"} <= derived

    def test_derived_rows_record_their_formula_as_the_tag(self, db, orcl_company, orcl_facts):
        with db() as session:
            statements.refresh_company(session, orcl_company, facts_json=orcl_facts)
            ebitda = session.execute(
                select(StatementFact).where(StatementFact.canonical_item == "ebitda")
                .order_by(StatementFact.fiscal_year.desc())).scalars().first()
        assert ebitda.xbrl_tag_used.startswith("derived:")
        assert "approximation" in ebitda.xbrl_tag_used  # EBITDA caveat is visible

    def test_refresh_replaces_rather_than_accumulates(self, db, orcl_company, orcl_facts):
        with db() as session:
            statements.refresh_company(session, orcl_company, facts_json=orcl_facts)
            first = session.execute(select(StatementFact)).scalars().all()
            statements.refresh_company(session, orcl_company, facts_json=orcl_facts)
            second = session.execute(select(StatementFact)).scalars().all()
        assert len(first) == len(second) > 0

    def test_refresh_recomputes_ratios(self, db, orcl_company, orcl_facts):
        with db() as session:
            statements.refresh_company(session, orcl_company, facts_json=orcl_facts)
            ratios = list(session.execute(select(Ratio)).scalars())

        assert ratios
        # Every stored ratio row carries a value or a reason, never neither.
        assert all((r.value is not None) or r.na_reason for r in ratios)
        roe_2023 = next(r for r in ratios if r.ratio_key == "roe" and r.fiscal_year == 2023)
        assert roe_2023.value is None
        assert roe_2023.na_reason == "non-positive average equity"
