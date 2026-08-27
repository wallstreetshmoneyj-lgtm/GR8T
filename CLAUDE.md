# Company Research Terminal

Single-user equity research terminal for the S&P 500: five fiscal years of SEC
XBRL statements, a full ratio library with comps, and filing links.
`SPEC.md` is the authoritative build handoff — read it before changing behavior.

**Phase 1 is built.** Phases 2-5 are not (see roadmap below).

## Stack

Python 3.11+ · FastAPI · server-rendered Jinja2 + vanilla JS (no React, no build
step) · SQLAlchemy 2.x on SQLite · APScheduler · httpx · pytest · ruff.

Every page's data is also a JSON endpoint under `/api/...`, so a fancier frontend
can be added later without touching the backend.

## Commands

```bash
pip install -r requirements.txt
cp .env.example .env          # fill in SEC_USER_AGENT at minimum
make run                      # uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`make run` is the one command: it creates tables, seeds companies from the CSV,
starts the scheduler, and (on an empty DB) kicks off the first full data load in
a background thread. Watch `/status` while it loads.

| Command | What it does |
|---|---|
| `make refresh` | Full manual refresh: filings + statements + ratios + coverage report |
| `python -m pipelines.run statements --tickers ORCL,MSFT` | Refresh named companies only |
| `python -m pipelines.run statements --from-cache` | Re-parse cached responses, no SEC requests |
| `make coverage` | Print the tag-mapping coverage summary |
| `make seed-peers` | Regenerate peers (writes `peers.candidate.json` if one exists) |
| `make refresh-universe` | Regenerate a candidate `sp500.csv` + diff, never overwrites |
| `make test` / `make lint` | pytest / ruff |

## Back this up

**`data/terminal.db`** — the SQLite file. It holds your research notes, which are
the only irreplaceable thing here (everything else re-fetches from SEC). Also
available: `GET /api/notes/export` returns all notes as one markdown file.

Disk: a fully loaded universe is roughly **500MB of database** (most of it the
complete EDGAR filing history — 1.8M rows, mostly Form 4s) plus **~2GB of raw
response cache**. The cache is disposable: `rm -rf data/cache` frees it, at the
cost of re-fetching on the next refresh. Fixed a parser bug instead? Use
`--from-cache` to re-parse everything without touching SEC.

## Data-source rules

**SEC fair-access policy is non-negotiable:**
- `SEC_USER_AGENT` must be a real name + email. Requests fail loudly without it.
- Max 10 req/sec across all SEC hosts; we throttle to ~5/sec in one shared
  limiter covering `data.sec.gov` and `www.sec.gov` (`pipelines/http_client.py`).
- Link out to filing documents; never mirror them.
- Every raw response is cached to `data/cache/` before parsing, so a parser bug
  never forces a re-fetch.

Other providers (all free tiers, keys in `.env`, never committed): Finnhub 60/min
(budget 30), FRED, CoinGecko. Damodaran industry data is linked with attribution.
**Never use Yahoo Finance or yfinance** — ToS violation and it breaks.

Page requests read from the DB only. Nothing fetches a third-party API inside a
request handler.

## Layout

```
app/       FastAPI routes (main.py), views.py (shared page data), api/, templates/, static/
core/      config.py (env), db.py (engine + all models)
pipelines/ http_client, edgar_client, xbrl_map, statements, ratios, filings,
           universe, alerts (dedupe only), scheduler, run.py (CLI)
data/      seed/sp500.csv, seed/peers.json, content/ratios.yml, cache/, reports/
scripts/   refresh_universe.py, make_fixtures.py
tests/     fixtures/ are trimmed real companyfacts/submissions JSON
```

## Things worth knowing before you edit

**Fiscal years in companyfacts.** A fact's `fy` field labels the *report* it
appeared in, not the fact's own period: a FY2026 10-K carries FY2026, FY2025 and
FY2024 comparatives all tagged `fy=2026`. `xbrl_map.build_fy_calendar()` therefore
anchors each 10-K accession to its own period-end date and assigns every fact its
fiscal year by period-end lookup. This is what makes the restatement rule work
(latest filed value wins per item-year).

**Tag chains fall back per fiscal year, not per company** — a company can use the
preferred tag one year and an older tag the next. `_first_in_chain` also prefers
the first *non-zero* value in a chain: filers sometimes leave a stray zero on a
high-priority tag while the real balance sits on a later one (Oracle's FY2022
`LongTermDebt=0` next to `LongTermNotesPayable=$72.1B`).

**Some filers never tag the total.** `_apply_computed_fallbacks` derives pretax
income from Domestic+Foreign, D&A from Depreciation+Amortization, and total
liabilities from assets−equity. These are marked `computed:` in `xbrl_tag_used`
and visible in each cell's tooltip. Separately, about a fifth of the index never
tags `OperatingIncomeLoss` (IBM among them), so the derived `ebit` falls back to
pretax income + interest expense — the derived item only; the operating income
*row* stays "-" rather than showing a number the company never reported.

**Where a number would mislead, prefer n/a.** Commercial banks tag gross interest
income, not comparable to revenue elsewhere in the table, so it is deliberately
unmapped: an honest "n/a" with a reason beats a number that wrecks a comparison.

**Coverage today:** 6.2% of core-item cells missing across the 500 companies
(target < 10%), zero fetch/parse errors. `make coverage` re-prints it;
`data/reports/xbrl_coverage.csv` lists every unmapped (company, item) pair. Some
misses are facts, not bugs — XOM, PSKY and HONA file under brand-new CIKs after
2025-26 reorganizations and have no 10-K history yet.

**Dual share classes share one CIK.** `companies` is keyed by cik, so GOOG/GOOGL,
FOX/FOXA and NWS/NWSA get one row each; `universe.ticker_aliases()` resolves the
other ticker to it, so both URLs work.

**Notes are sacred.** No job, refresh, or migration may modify or delete rows in
the `notes` table. Pipelines never import `Note`. The only deletion path is the
confirmed UI action → `DELETE /api/notes/{id}`. `tests/test_notes_persistence.py`
enforces this by running real refreshes and diffing the rows.

**Ratio n/a is data, not an error.** Every ratio stores either a value or an
`na_reason` (never both, never neither) — "non-positive average equity", "no
inventory", "non-positive denominator". Pages render the reason. Missing data
renders `-` or `n/a`; it must never 500.

**Seed files are hand-maintained.** `sp500.csv` and `peers.json` are never
auto-overwritten; the generators write `*.candidate.*` siblings for review.

## Roadmap

- **Phase 1 (done)** — universe seed, EDGAR pipelines, canonical mapping, 5yr
  statements, fiscal ratios + comps, filings tab, notes, `/status`.
- **Phase 2** — prices + news (Finnhub), watchlist, market-data ratios on pages
  (the math already exists in `ratios.compute_market_ratios`), sector prices.
- **Phase 3** — earnings calendar, alert engine + SMTP delivery (dedupe ledger
  already in `pipelines/alerts.py`), watchlist alert toggles.
- **Phase 4** — macro page: FRED series, the rules-based economy indicator
  (SPEC 10.4), release calendar, treasury + crypto strips.
- **Phase 5** — LLM company descriptions from 10-K Item 1, feature-flagged; the
  site must still run without an Anthropic key. Check https://docs.claude.com for
  current model/API details before implementing.

## Owner to-dos (SPEC 17)

Write the `description:` fields in `data/content/ratios.yml` (they render as
"description coming soon" until then) · fill `ir_url` in `sp500.csv` · review
`peers.json` · get Finnhub + FRED keys · pick a site name for the header.
