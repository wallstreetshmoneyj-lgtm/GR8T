"""SEC EDGAR fetchers: companyfacts, submissions, ticker->CIK map, doc URLs.

All requests go through the shared http_client (rate-limited to <= 5/sec
across every SEC host, User-Agent from SEC_USER_AGENT, raw responses cached
under data/cache/sec/).
"""
from __future__ import annotations

from pipelines import http_client

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/{name}"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ARCHIVE_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodashes}/{primary_doc}"


def cik10(cik: str | int) -> str:
    """Zero-padded 10-digit CIK string."""
    return str(int(cik)).zfill(10)


def fetch_companyfacts(cik: str | int) -> dict:
    c = cik10(cik)
    return http_client.get_json(
        COMPANYFACTS_URL.format(cik10=c), "sec", cache_key=f"companyfacts_CIK{c}.json"
    )


def fetch_submissions(cik: str | int) -> dict:
    """Full submissions index for a company.

    The primary JSON holds the most recent ~1000 filings; older history is
    split into extra files listed under filings.files. We fetch those too so
    the filings tab really is the full EDGAR history, and merge everything
    into one 'recent'-shaped dict of parallel column lists.
    """
    c = cik10(cik)
    data = http_client.get_json(
        SUBMISSIONS_URL.format(name=f"CIK{c}.json"), "sec", cache_key=f"submissions_CIK{c}.json"
    )
    recent = data.get("filings", {}).get("recent", {})
    for extra in data.get("filings", {}).get("files", []):
        name = extra.get("name")
        if not name:
            continue
        older = http_client.get_json(
            SUBMISSIONS_URL.format(name=name), "sec", cache_key=f"submissions_{name}"
        )
        # Older pages are column-list dicts with the same keys as 'recent'.
        for key, values in older.items():
            if isinstance(values, list) and isinstance(recent.get(key), list):
                recent[key].extend(values)
    return data


def fetch_company_tickers() -> dict:
    """SEC's ticker -> CIK mapping file (used by the universe seed script)."""
    return http_client.get_json(COMPANY_TICKERS_URL, "sec", cache_key="company_tickers.json")


def archive_doc_url(cik: str | int, accession: str, primary_doc: str) -> str:
    """Direct link to a filing's primary document on SEC Archives (link out
    only — we never mirror documents)."""
    return ARCHIVE_DOC_URL.format(
        cik_int=int(cik),
        accession_nodashes=accession.replace("-", ""),
        primary_doc=primary_doc,
    )
