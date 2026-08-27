"""Generate a candidate data/seed/sp500.csv from Wikipedia's S&P 500
constituents table, cross-checked against SEC's company_tickers.json.

This is a one-time/occasional SEED script, not a live scraper (SPEC 5):
- If sp500.csv does not exist yet, it is written directly.
- If it exists, sp500.candidate.csv is written and a diff is printed for
  manual review. The real file is NEVER auto-overwritten.
- Any ticker that can't be matched to a CIK in SEC's mapping fails loudly.

Run via `make refresh-universe` or `python -m scripts.refresh_universe`.
"""
from __future__ import annotations

import csv
import difflib
import sys
from html.parser import HTMLParser
from pathlib import Path

from core.config import settings
from pipelines import edgar_client, http_client

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
CSV_COLUMNS = ["ticker", "company_name", "cik", "gics_sector", "gics_sub_industry",
               "ir_url", "active"]


class _ConstituentsTableParser(HTMLParser):
    """Extract rows of the table with id="constituents" (stdlib only; the
    seed is one-time so a heavier HTML dependency isn't warranted)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.table_depth = 0
        self.in_cell = False
        self.rows: list[list[str]] = []
        self._row: list[str] = []
        self._cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if dict(attrs).get("id") == "constituents":
                self.in_table = True
                self.table_depth = 0
            elif self.in_table:
                self.table_depth += 1  # nested table (shouldn't happen, but be safe)
        if not self.in_table or self.table_depth:
            return
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self.in_cell = True
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.in_table:
            if self.table_depth:
                self.table_depth -= 1
            else:
                self.in_table = False
        if not self.in_table or self.table_depth:
            return
        if tag in ("td", "th"):
            self.in_cell = False
            self._row.append(" ".join("".join(self._cell).split()))
        elif tag == "tr" and self._row:
            self.rows.append(self._row)

    def handle_data(self, data: str) -> None:
        if self.in_table and not self.table_depth and self.in_cell:
            self._cell.append(data)


def _fetch_wiki_html() -> str:
    """Fetch the constituents page, falling back to the cached copy.

    Wikimedia's edge sometimes 403s non-browser HTTP clients even with a
    polite User-Agent. Since this is a one-time seed (not a live scraper),
    the workaround is manual and boring: fetch the page with curl into the
    cache location and re-run this script.
    """
    cache_file = settings.cache_dir / "misc" / "wikipedia_sp500.html"
    try:
        return http_client.get(WIKI_URL, "misc", cache_key="wikipedia_sp500.html").decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        if cache_file.exists():
            print(f"fetch failed ({exc}); using cached copy at {cache_file}")
            return cache_file.read_text()
        raise SystemExit(
            f"FAILED to fetch the Wikipedia page ({exc}) and no cached copy exists.\n"
            f"Manual path:  mkdir -p {cache_file.parent} && "
            f"curl -o {cache_file} '{WIKI_URL}'  then re-run this script."
        ) from exc


def fetch_constituents() -> list[dict[str, str]]:
    html = _fetch_wiki_html()
    parser = _ConstituentsTableParser()
    parser.feed(html)
    if not parser.rows:
        raise RuntimeError("could not find the constituents table on the Wikipedia page")
    header = [h.lower() for h in parser.rows[0]]

    def col(name_fragment: str) -> int:
        for i, h in enumerate(header):
            if name_fragment in h:
                return i
        raise RuntimeError(f"column '{name_fragment}' not found in {header}")

    i_symbol, i_name = col("symbol"), col("security")
    i_sector, i_sub = col("gics sector"), col("gics sub")
    i_cik = col("cik")
    out = []
    for row in parser.rows[1:]:
        if len(row) <= max(i_symbol, i_name, i_sector, i_sub, i_cik):
            continue
        out.append({
            # Class shares: Wikipedia uses BRK.B, SEC uses BRK-B; normalize to dashes.
            "ticker": row[i_symbol].replace(".", "-").upper(),
            "company_name": row[i_name],
            "gics_sector": row[i_sector],
            "gics_sub_industry": row[i_sub],
            "cik": row[i_cik].zfill(10),
        })
    return out


def cross_check_ciks(constituents: list[dict[str, str]]) -> None:
    """Verify every ticker's CIK against SEC's own mapping; fail loudly on
    misses (SPEC 5). Wikipedia's CIK column is usually right — the SEC file
    is the authority when they disagree."""
    sec_map = edgar_client.fetch_company_tickers()
    by_ticker = {entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
                 for entry in sec_map.values()}
    misses, fixes = [], 0
    for row in constituents:
        sec_cik = by_ticker.get(row["ticker"])
        if sec_cik is None:
            misses.append(row["ticker"])
        elif sec_cik != row["cik"]:
            row["cik"] = sec_cik
            fixes += 1
    if misses:
        raise SystemExit(
            f"FAILED: {len(misses)} tickers not found in SEC company_tickers.json: "
            f"{', '.join(sorted(misses))}\nFix the tickers (or SEC mapping lag) and re-run."
        )
    print(f"CIK cross-check ok ({fixes} corrected from SEC mapping)")


def write_csv(constituents: list[dict[str, str]], existing: Path) -> None:
    constituents = sorted(constituents, key=lambda r: r["ticker"])
    target = existing if not existing.exists() else existing.with_name("sp500.candidate.csv")
    existing.parent.mkdir(parents=True, exist_ok=True)

    # Preserve owner-maintained ir_url values on regeneration.
    ir_urls: dict[str, str] = {}
    if existing.exists():
        with open(existing, newline="") as f:
            ir_urls = {row["ticker"]: row.get("ir_url", "") for row in csv.DictReader(f)}

    with open(target, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in constituents:
            writer.writerow({**row, "ir_url": ir_urls.get(row["ticker"], ""), "active": "true"})
    print(f"wrote {target} ({len(constituents)} companies)")

    if target != existing:
        old = existing.read_text().splitlines(keepends=True)
        new = target.read_text().splitlines(keepends=True)
        diff = list(difflib.unified_diff(old, new, str(existing), str(target)))
        print("".join(diff) if diff else "no changes vs current sp500.csv")
        print("\nReview the diff, then replace sp500.csv manually if it looks right.")


def main() -> None:
    constituents = fetch_constituents()
    if not 480 <= len(constituents) <= 520:
        sys.exit(f"FAILED: parsed {len(constituents)} rows — expected ~503; "
                 "the Wikipedia table layout may have changed.")
    cross_check_ciks(constituents)
    write_csv(constituents, settings.seed_dir / "sp500.csv")


if __name__ == "__main__":
    main()
