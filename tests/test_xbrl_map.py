"""xbrl_map tests: fallback selection, annual-duration filtering, fiscal-year
assignment, restatement handling — against a hand-built synthetic
companyfacts document (exact control) and real trimmed fixtures (SPEC 15)."""
from __future__ import annotations

import pytest

from pipelines.xbrl_map import parse_companyfacts


def _fact(start: str | None, end: str, val: float, accn: str, fy: int,
          filed: str, form: str = "10-K", fp: str = "FY") -> dict:
    fact = {"end": end, "val": val, "accn": accn, "fy": fy, "fp": fp,
            "form": form, "filed": filed}
    if start:
        fact["start"] = start
    return fact


def synthetic_companyfacts() -> dict:
    """Calendar-year filer with two 10-Ks (FY2024 filed 2025, FY2025 filed
    2026), one restatement, one quarterly stub, one 10-Q fact, one stray
    zero-valued debt tag."""
    a23, a24, a25 = "0001-23-000001", "0001-24-000001", "0001-25-000001"
    return {"cik": 1, "entityName": "Synthetic Corp", "facts": {"us-gaap": {
        # Anchor + fallback target. FY2025 10-K restates FY2024 100 -> 105.
        "Revenues": {"units": {"USD": [
            _fact("2022-01-01", "2022-12-31", 80.0, a23, 2023, "2024-02-01"),
            _fact("2023-01-01", "2023-12-31", 90.0, a23, 2023, "2024-02-01"),
            _fact("2023-01-01", "2023-12-31", 90.0, a24, 2024, "2025-02-01"),
            _fact("2024-01-01", "2024-12-31", 100.0, a24, 2024, "2025-02-01"),
            _fact("2024-10-01", "2024-12-31", 30.0, a24, 2024, "2025-02-01"),  # Q4 stub
            _fact("2024-01-01", "2024-12-31", 105.0, a25, 2025, "2026-02-01"),  # restated
            _fact("2025-01-01", "2025-12-31", 110.0, a25, 2025, "2026-02-01"),
            _fact("2025-01-01", "2025-06-30", 60.0, a25, 2025, "2026-02-01", form="10-Q", fp="Q2"),
        ]}},
        # Higher-priority revenue tag exists ONLY for FY2025 — fallback must
        # be per-fiscal-year, not per-company.
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            _fact("2025-01-01", "2025-12-31", 111.0, a25, 2025, "2026-02-01"),
        ]}},
        "Assets": {"units": {"USD": [
            _fact(None, "2023-12-31", 900.0, a23, 2023, "2024-02-01"),
            _fact(None, "2024-12-31", 1000.0, a24, 2024, "2025-02-01"),
            _fact(None, "2025-12-31", 1100.0, a25, 2025, "2026-02-01"),
            _fact(None, "2024-12-31", 1000.0, a25, 2025, "2026-02-01"),  # comparative
        ]}},
        # ~200-day duration must be excluded by the annual filter.
        "NetIncomeLoss": {"units": {"USD": [
            _fact("2025-01-01", "2025-12-31", 20.0, a25, 2025, "2026-02-01"),
            _fact("2025-06-01", "2025-12-18", 12.0, a25, 2025, "2026-02-01"),
        ]}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": [
            _fact("2025-01-01", "2025-12-31", 2.0, a25, 2025, "2026-02-01"),
        ]}},
        "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [
            _fact("2025-01-01", "2025-12-31", 10.0, a25, 2025, "2026-02-01"),
        ]}},
        # Stray zero on the higher-priority tag; the real balance is on the
        # lower-priority tag — non-zero preference must pick 500.
        "LongTermDebt": {"units": {"USD": [
            _fact(None, "2025-12-31", 0.0, a25, 2025, "2026-02-01"),
        ]}},
        "LongTermNotesPayable": {"units": {"USD": [
            _fact(None, "2025-12-31", 500.0, a25, 2025, "2026-02-01"),
        ]}},
    }}}


@pytest.fixture(scope="module")
def synthetic():
    result = parse_companyfacts(synthetic_companyfacts())
    return {(f.item, f.fiscal_year): f for f in result.facts}


class TestSynthetic:
    def test_fallback_is_per_fiscal_year(self, synthetic):
        # FY2025 has the preferred tag; FY2024/FY2023 fall back to Revenues.
        assert synthetic[("revenue", 2025)].value == 111.0
        assert synthetic[("revenue", 2025)].tag == "RevenueFromContractWithCustomerExcludingAssessedTax"
        assert synthetic[("revenue", 2024)].tag == "Revenues"
        assert synthetic[("revenue", 2023)].value == 90.0

    def test_restatement_latest_filed_wins(self, synthetic):
        # FY2024 revenue: 100 in the FY2024 10-K, restated to 105 in the
        # FY2025 10-K (filed later) — the restated value wins.
        assert synthetic[("revenue", 2024)].value == 105.0
        assert str(synthetic[("revenue", 2024)].filed) == "2026-02-01"

    def test_quarterly_stub_and_short_duration_excluded(self, synthetic):
        # The Q4 stub (92 days) and the 200-day duration never surface.
        assert synthetic[("revenue", 2024)].value != 30.0
        assert synthetic[("net_income", 2025)].value == 20.0

    def test_non_10k_forms_ignored(self, synthetic):
        assert synthetic[("revenue", 2025)].value != 60.0

    def test_comparative_instants_map_to_their_own_year(self, synthetic):
        assert synthetic[("total_assets", 2025)].value == 1100.0
        assert synthetic[("total_assets", 2024)].value == 1000.0

    def test_units_respected(self, synthetic):
        assert synthetic[("eps_diluted", 2025)].value == 2.0
        assert synthetic[("eps_diluted", 2025)].unit == "USD/shares"
        assert synthetic[("shares_diluted", 2025)].unit == "shares"

    def test_nonzero_preference_over_stray_zero(self, synthetic):
        fact = synthetic[("long_term_debt", 2025)]
        assert fact.value == 500.0
        assert fact.tag == "LongTermNotesPayable"


class TestRealFixtures:
    """Trimmed real companyfacts (values verifiable against the filed 10-Ks)."""

    def test_orcl_five_years_of_revenue(self, orcl_facts):
        result = parse_companyfacts(orcl_facts)
        revenue = {f.fiscal_year: f.value for f in result.facts if f.item == "revenue"}
        assert revenue[2026] == 67_357_000_000
        assert revenue[2025] == 57_399_000_000
        assert revenue[2024] == 52_961_000_000
        assert revenue[2023] == 49_954_000_000
        assert revenue[2022] == 42_440_000_000

    def test_orcl_fiscal_year_ends_in_may(self, orcl_facts):
        result = parse_companyfacts(orcl_facts)
        fy26 = next(f for f in result.facts if f.item == "revenue" and f.fiscal_year == 2026)
        assert str(fy26.period_end) == "2026-05-31"

    def test_orcl_negative_equity_year_mapped(self, orcl_facts):
        result = parse_companyfacts(orcl_facts)
        equity = {f.fiscal_year: f.value for f in result.facts if f.item == "total_equity"}
        assert equity[2022] < 0  # the ROE-null golden path depends on this

    def test_msft_maps_all_core_items(self, msft_facts):
        result = parse_companyfacts(msft_facts)
        items = {f.item for f in result.facts}
        for core in ["revenue", "operating_income", "net_income", "total_assets",
                     "total_equity", "cfo", "capex", "inventory"]:
            assert core in items, f"{core} unmapped for MSFT"

    def test_ibm_parses_without_errors(self, ibm_facts):
        result = parse_companyfacts(ibm_facts)
        assert len(result.fiscal_years) == 6
        assert any(f.item == "revenue" for f in result.facts)

    def test_missing_items_reported(self, orcl_facts):
        # Oracle reports no gross-profit or cost-of-revenue line — the
        # coverage report must say so rather than inventing values.
        result = parse_companyfacts(orcl_facts)
        assert "cost_of_revenue" in result.missing_items
        assert "gross_profit" in result.missing_items
