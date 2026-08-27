"""Ratio engine golden tests (SPEC 15).

Expected values are hand-computed from the figures in the companies' own
10-K filings and written here as literals — they are NOT produced by running
the engine, which is what makes these golden tests rather than change
detectors. The arithmetic behind each literal is shown in a comment.

ORCL is the negative-equity / no-inventory case; MSFT is the normal-equity
case with inventory.
"""
from __future__ import annotations

import pytest

from pipelines.ratios import compute_fiscal_ratios, compute_market_ratios
from pipelines.statements import build_values
from pipelines.xbrl_map import parse_companyfacts

TOL = 1e-6


@pytest.fixture(scope="module")
def orcl(orcl_facts):
    return build_values(parse_companyfacts(orcl_facts))


@pytest.fixture(scope="module")
def msft(msft_facts):
    return build_values(parse_companyfacts(msft_facts))


def value(ratios: dict, key: str) -> float | None:
    return ratios[key][0]


def reason(ratios: dict, key: str) -> str | None:
    return ratios[key][1]


class TestOracleFY2026:
    """Oracle FY2026 (fiscal year ended 2026-05-31), $M from the 10-K:
    current assets 46,567 · current liabilities 41,764 · cash 31,289
    ST investments 605 · revenue 67,357 · net income 17,087 · avg AR 9,471.5
    avg equity 32,012.5 · avg invested capital 121,518.5 · CFO 31,977
    capex 55,663 · EBITDA 29,900 · diluted shares 2,914 · diluted EPS 5.83
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def r(orcl):
        return compute_fiscal_ratios(orcl, 2026)

    def test_current_ratio(self, r):
        # 46,567 / 41,764 = 1.1150033521693323
        assert value(r, "current_ratio") == pytest.approx(1.1150033521693323, abs=TOL)

    def test_quick_ratio_equals_current_ratio_without_inventory(self, r):
        # Oracle reports no inventory line, so (CA - 0) / CL == current ratio.
        assert value(r, "quick_ratio") == pytest.approx(1.1150033521693323, abs=TOL)

    def test_cash_ratio(self, r):
        # (31,289 + 605) / 41,764 = 0.7636720620630207
        assert value(r, "cash_ratio") == pytest.approx(0.7636720620630207, abs=TOL)

    def test_dso(self, r):
        # 365 / (67,357 / 9,471.5) = 365 x 9,471.5 / 67,357 = 51.324992205709876
        assert value(r, "dso") == pytest.approx(51.324992205709876, abs=1e-6)

    def test_roic(self, r):
        # NOPAT 18,006.276056 / avg invested capital 121,518.5 = 0.1481772409637208
        assert value(r, "roic") == pytest.approx(0.1481772409637208, abs=TOL)

    def test_roe_positive_in_fy2026(self, r):
        # 17,087 / 32,012.5 = 0.5337602499023819 (equity recovered by FY2026)
        assert value(r, "roe") == pytest.approx(0.5337602499023819, abs=TOL)

    def test_net_margin(self, r):
        # 17,087 / 67,357 = 0.2536781626260077
        assert value(r, "net_margin") == pytest.approx(0.2536781626260077, abs=TOL)

    def test_fcf_margin_is_negative_on_ai_capex(self, r):
        # (31,977 - 55,663) / 67,357 = -0.351648677939932
        assert value(r, "fcf_margin") == pytest.approx(-0.351648677939932, abs=TOL)

    def test_ebitda_margin(self, r):
        # 29,900 / 67,357 = 0.4439033804949745
        assert value(r, "ebitda_margin") == pytest.approx(0.4439033804949745, abs=TOL)

    def test_inventory_ratios_are_na_with_reason(self, r):
        # SPEC 10.2: missing/zero inventory -> null "no inventory".
        assert value(r, "inventory_turnover") is None
        assert reason(r, "inventory_turnover") == "no inventory"
        assert value(r, "dio") is None
        assert reason(r, "dio") == "no inventory"

    def test_ccc_inherits_the_inventory_reason(self, r):
        assert value(r, "ccc") is None
        assert reason(r, "ccc") == "no inventory"


class TestOracleNegativeEquityYear:
    """FY2023 average equity is negative (-2,106 $M) after years of
    buybacks — the ROE null path the acceptance criteria call for."""

    @pytest.fixture(scope="class")
    @staticmethod
    def r(orcl):
        return compute_fiscal_ratios(orcl, 2023)

    def test_roe_is_na_with_reason(self, r):
        assert value(r, "roe") is None
        assert reason(r, "roe") == "non-positive average equity"

    def test_equity_multiplier_is_na_too(self, r):
        assert value(r, "equity_multiplier") is None
        assert reason(r, "equity_multiplier") == "non-positive average equity"

    def test_sgr_inherits_the_roe_reason(self, r):
        assert value(r, "sgr") is None
        assert reason(r, "sgr") == "non-positive average equity"

    def test_ratios_not_depending_on_equity_still_compute(self, r):
        # 21,004 / 23,090 = 0.9096578605456908
        assert value(r, "current_ratio") == pytest.approx(0.9096578605456908, abs=TOL)
        assert value(r, "net_margin") is not None


class TestMicrosoftFY2026:
    """Normal-equity comparison case. MSFT FY2026 ($M): current assets
    207,710 · current liabilities 168,825 · inventory 1,397 · cash 20,935
    ST investments 55,908 · revenue 331,839 · net income 133,749
    avg equity 392,933 · avg inventory 1,167.5 · cost of revenue 106,374
    avg AR 75,390.5 · avg invested capital 348,951.5
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def r(msft):
        return compute_fiscal_ratios(msft, 2026)

    def test_current_ratio(self, r):
        # 207,710 / 168,825 = 1.2303272619576484
        assert value(r, "current_ratio") == pytest.approx(1.2303272619576484, abs=TOL)

    def test_quick_ratio_excludes_inventory(self, r):
        # (207,710 - 1,397) / 168,825 = 1.2220524211461572
        assert value(r, "quick_ratio") == pytest.approx(1.2220524211461572, abs=TOL)
        assert value(r, "quick_ratio") < value(r, "current_ratio")

    def test_cash_ratio(self, r):
        # (20,935 + 55,908) / 168,825 = 0.45516363097882423
        assert value(r, "cash_ratio") == pytest.approx(0.45516363097882423, abs=TOL)

    def test_roe_computes_on_positive_equity(self, r):
        # 133,749 / 392,933 = 0.3403862745048138
        assert value(r, "roe") == pytest.approx(0.3403862745048138, abs=TOL)
        assert reason(r, "roe") is None

    def test_roic(self, r):
        # NOPAT 125,126.818572 / avg invested capital 348,951.5 = 0.3585793973444575
        assert value(r, "roic") == pytest.approx(0.3585793973444575, abs=TOL)

    def test_inventory_turnover_and_dio(self, r):
        # 106,374 / 1,167.5 = 91.11263383297644 ; 365 / that = 4.006030608983398
        assert value(r, "inventory_turnover") == pytest.approx(91.11263383297644, abs=1e-6)
        assert value(r, "dio") == pytest.approx(4.006030608983398, abs=1e-6)

    def test_dso(self, r):
        # 365 x 75,390.5 / 331,839 = 82.92434734916631
        assert value(r, "dso") == pytest.approx(82.92434734916631, abs=1e-6)


class TestMarketRatiosWithStubbedPrice:
    """EV math against a stubbed price (SPEC 15). ORCL FY2026 fundamentals,
    price fixed at $250.00 so the arithmetic is checkable by hand."""

    @pytest.fixture(scope="class")
    @staticmethod
    def r(orcl):
        latest = {item: years.get(2026) for item, years in orcl.items()}
        return compute_market_ratios(250.0, latest)

    def test_market_cap(self, r):
        # 250.00 x 2,914M shares = 728,500 $M
        assert value(r, "market_cap") == pytest.approx(728_500_000_000, abs=1.0)

    def test_enterprise_value(self, r):
        # 728,500 + total debt 129,541 - cash 31,289 - ST inv 605 = 826,147 $M
        assert value(r, "ev") == pytest.approx(826_147_000_000, abs=1.0)

    def test_pe(self, r):
        # 250.00 / 5.83 = 42.88164665523156
        assert value(r, "pe") == pytest.approx(42.88164665523156, abs=1e-6)

    def test_ev_ebitda(self, r):
        # 826,147 / 29,900 = 27.630334448160536
        assert value(r, "ev_ebitda") == pytest.approx(27.630334448160536, abs=1e-6)

    def test_ev_sales(self, r):
        # 826,147 / 67,357 = 12.265198865745209
        assert value(r, "ev_sales") == pytest.approx(12.265198865745209, abs=1e-6)

    def test_negative_fcf_multiples_are_na(self, r):
        # FY2026 FCF is -23,686 $M — a multiple off it is not meaningful.
        assert value(r, "p_fcf") is None
        assert reason(r, "p_fcf") == "non-positive denominator"
        assert value(r, "ev_fcf") is None
        assert reason(r, "ev_fcf") == "non-positive denominator"

    def test_peg_requires_positive_growth(self, orcl):
        latest = {item: years.get(2026) for item, years in orcl.items()}
        # No ni_yoy supplied -> PEG must be n/a, never a divide-by-zero crash.
        assert compute_market_ratios(250.0, latest)["peg"] == (
            None, "requires positive net income growth")
        # With growth supplied: PE 42.88164665523156 / (0.3731 x 100) = 1.1493...
        latest["ni_yoy"] = 0.3731
        peg = compute_market_ratios(250.0, latest)["peg"][0]
        assert peg == pytest.approx(42.88164665523156 / 37.31, abs=1e-6)


class TestNaReasonsAreAlwaysPopulated:
    def test_every_ratio_has_exactly_one_of_value_or_reason(self, orcl, msft):
        for vals, fy in [(orcl, 2026), (orcl, 2023), (msft, 2026)]:
            for key, (val, why) in compute_fiscal_ratios(vals, fy).items():
                assert (val is None) != (why is None), (
                    f"{key} FY{fy} must have exactly one of value/na_reason, got {val!r}/{why!r}")

    def test_no_ratio_raises_on_an_empty_company(self):
        # Graceful degradation: a company with no facts must yield all-n/a,
        # never an exception (SPEC 15).
        results = compute_fiscal_ratios({}, 2026)
        assert results
        assert all(val is None and why for val, why in results.values())
