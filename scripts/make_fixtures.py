"""Regenerate the trimmed companyfacts/submissions fixtures in tests/fixtures/.

Trims cached SEC responses (data/cache/sec/) down to the tags the mapper
reads, so fixtures stay small enough to commit while keeping the real JSON
structure. Run after a refresh if fixtures ever need updating:
    python -m scripts.make_fixtures
"""
from __future__ import annotations

import json
from pathlib import Path

from core.config import settings
from pipelines import xbrl_map

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
TICKER_CIKS = {"ORCL": "0001341439", "MSFT": "0000789019", "IBM": "0000051143",
               "CRM": "0001108524"}

EXTRA_TAGS = [
    # computed-fallback and anchor tags the mapper also reads
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesForeign",
    "Depreciation", "AmortizationOfIntangibleAssets",
    "LiabilitiesAndStockholdersEquity",
]


def wanted_tags() -> set[str]:
    tags = set(EXTRA_TAGS)
    for _, items in xbrl_map.STATEMENTS:
        for _, chain in items:
            tags.update(chain)
    return tags


# Facts ending before this are dropped: the mapper only ever looks at the six
# most recent fiscal years, and full history makes the fixtures megabytes.
EARLIEST_PERIOD_END = "2018-01-01"


def trim_companyfacts(ticker: str, cik: str) -> None:
    src = settings.cache_dir / "sec" / f"companyfacts_CIK{cik}.json"
    data = json.loads(src.read_text())
    keep = wanted_tags()
    gaap = data.get("facts", {}).get("us-gaap", {})

    trimmed: dict[str, dict] = {}
    for tag in sorted(keep):
        tag_data = gaap.get(tag)
        if not tag_data:
            continue
        units = {}
        for unit, facts in tag_data.get("units", {}).items():
            recent = [f for f in facts if (f.get("end") or "") >= EARLIEST_PERIOD_END]
            if recent:
                units[unit] = recent
        if units:
            trimmed[tag] = {**tag_data, "units": units}

    data["facts"] = {"us-gaap": trimmed}
    out = FIXTURES_DIR / f"companyfacts_{ticker}.json"
    out.write_text(json.dumps(data, separators=(",", ":")))
    print(f"{out}: {out.stat().st_size / 1024:.0f} KB, {len(trimmed)} tags")


# Keep enough of each form that the filings tab, its filter chips, and the
# latest/prior 10-K links all have something real to render in tests.
FORM_QUOTAS = {"10-K": 4, "10-Q": 6, "8-K": 6, "DEF 14A": 2, "4": 10}


def trim_submissions(ticker: str, cik: str) -> None:
    src = settings.cache_dir / "sec" / f"submissions_CIK{cik}.json"
    data = json.loads(src.read_text())
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])

    quotas = dict(FORM_QUOTAS)
    keep: list[int] = []
    for i, form in enumerate(forms):
        if quotas.get(form, 0) > 0:
            quotas[form] -= 1
            keep.append(i)
    keep.sort()

    for key, values in list(recent.items()):
        if isinstance(values, list) and len(values) == len(forms):
            recent[key] = [values[i] for i in keep]
    data["filings"]["files"] = []
    out = FIXTURES_DIR / f"submissions_{ticker}.json"
    out.write_text(json.dumps(data, separators=(",", ":")))
    kept_forms = sorted({forms[i] for i in keep})
    print(f"{out}: {out.stat().st_size / 1024:.0f} KB, {len(keep)} filings, forms={kept_forms}")


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for ticker in ("ORCL", "MSFT", "IBM"):
        trim_companyfacts(ticker, TICKER_CIKS[ticker])
    trim_submissions("ORCL", TICKER_CIKS["ORCL"])


if __name__ == "__main__":
    main()
