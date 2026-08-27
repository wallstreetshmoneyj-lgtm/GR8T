# Company Research Terminal - Build Handoff
Owner: Joshua Lacroix (solo user, solo developer)
Date: 2026-08-26
Status: Greenfield. Nothing exists yet except this spec.
## 0. Instructions for Claude Code
1. Read this entire document before writing any code.
2. Build Phase 1 only (Section 12). Do not scaffold later phases beyond leaving clean seams for them.
3. Before coding, reply with a short build plan (file list, order of work, anything you would do differently). Wait for approval on deviations from this spec; proceed without asking on things the spec already decides.
4. Generate a CLAUDE.md at repo root summarizing: stack, commands to run, data-source rules (especially SEC fair-access), and the phase roadmap. Keep it under 150 lines.
5. Commit in small increments with clear messages. Write tests where Section 15 requires them.
6. The owner reads Python comfortably (has built backtesting engines) but is newer to web development. Prefer boring, readable code over clever code. Explain any non-obvious architectural choice in comments.
## 1. What this is
A single-user equity research terminal. It aggregates, for roughly the S&P 500 universe:
- Company overview: description, sector/industry, curated comparable companies
- Five fiscal years of income statement, balance sheet, and cash flow statement with year-over-year percent change columns, sourced from SEC XBRL
- A full ratio library computed per company, grouped by category, each with a plain-English description, and a comps view showing the same ratio across peer companies
- Direct links to filings: latest and prior 10-K prominently, full EDGAR history on a filings tab, plus the company IR page
- Delayed prices, recent company news, watchlist with news and earnings alerts
- Macro panel: GDP, CPI, payrolls with a rules-based heating/cooling/stable indicator, an economic release calendar, treasury yields, and a crypto price strip (prices only)
It is a research tool for fundamental analysis, not a trading tool. Freshness target is minutes, not milliseconds.
## 2. Hard constraints
- Single user. No accounts, no auth, no multi-tenancy. The watchlist has one implicit owner.
- Free data sources only. Primary sources (EDGAR, FRED) preferred over aggregators.
- Universe: S&P 500 constituents only for v1, from a static seed file. No on-demand universe expansion.
- No Yahoo Finance scraping and no yfinance. It violates ToS and breaks.
- Respect every provider's rate limits with margin (Section 6). Never fetch third-party APIs synchronously inside a page request except the narrow cases in Section 8.
- "Live" means: watchlist prices/news refresh hourly; everything else nightly or event-driven. This is a research terminal, not an active feed (the owner trades elsewhere). No websockets, no streaming.
- Development environment is GitHub Codespaces (owner is on a Chromebook until a Windows laptop arrives). Everything must run with `pip install -r requirements.txt` and one run command. No Docker requirement for v1 (a Dockerfile is fine to include but must not be the only path).
## 3. Tech stack (decided, do not relitigate)
- Python 3.11+
- FastAPI for the web app
- Server-rendered Jinja2 templates + minimal vanilla JS. No React in v1. Every page's data must also be available as a JSON endpoint under /api/... so a fancier frontend can be added later without backend changes.
- SQLite via SQLAlchemy 2.x (schema portable to Postgres later; no SQLite-only features)
- APScheduler for in-process scheduled jobs
- httpx for all outbound HTTP (with retries and timeouts)
- pytest for tests
- Plain CSS, one stylesheet, dark theme, monospace-friendly tables. Keep it simple and dense, closer to a terminal than a marketing site.
## 4. Repo layout
```
company-research-terminal/
  CLAUDE.md
  SPEC.md                  (this file)
  requirements.txt
  .env.example
  app/
    main.py                (FastAPI app, routes)
    templates/             (Jinja2)
    static/
    api/                   (JSON route modules)
  core/
    db.py                  (engine, session, models)
    config.py              (env loading)
  data/
    seed/sp500.csv         (ticker, company_name, cik, gics_sector, gics_sub_industry, ir_url)
    seed/peers.json        (ticker -> [peer tickers])
    content/ratios.yml     (ratio metadata + descriptions, Section 10)
  pipelines/
    edgar_client.py
    xbrl_map.py            (tag fallback chains)
    statements.py          (build 5yr statements)
    ratios.py              (ratio engine)
    filings.py             (filing index links)
    prices.py              (Phase 2)
    news.py                (Phase 2)
    macro.py               (Phase 4)
    scheduler.py           (job definitions)
  tests/
```
## 5. Universe seed
- Generate data/seed/sp500.csv once during setup from the current S&P 500 constituent list (Wikipedia's table is acceptable for this one-time seed; do not build a live scraper). Columns: ticker, company_name, cik (zero-padded 10 digits), gics_sector, gics_sub_industry, ir_url (blank allowed), active (bool).
- CIK mapping: cross-check tickers against https://www.sec.gov/files/company_tickers.json and fail loudly on misses.
- The file is manually maintained thereafter. Add a `make refresh-universe` script that regenerates a candidate CSV and prints a diff for manual review; it must never auto-overwrite.
- ir_url starts blank; owner will fill in over time. Pages must render fine without it.
## 6. Data sources, endpoints, and limits
| Purpose | Source | Endpoint pattern | Limit / rule |
|---|---|---|---|
| Financial statements (5yr) | SEC EDGAR XBRL | https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json | Max 10 req/sec across ALL SEC endpoints; nightly batch must throttle to <= 5/sec. REQUIRED header: User-Agent from env SEC_USER_AGENT |
| Filing history + doc links | SEC EDGAR submissions | https://data.sec.gov/submissions/CIK{cik10}.json | Same SEC rules |
| Filing documents | SEC Archives | https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodashes}/{primary_doc} | Link out only; do not mirror documents |
| Quotes (delayed ok) | Finnhub /quote | api key in env | Free tier 60 calls/min; budget max 30/min sustained |
| Company news | Finnhub /company-news | api key in env | Same budget |
| Earnings calendar | Finnhub /calendar/earnings | api key in env | Nightly fetch only |
| Macro series | FRED | series: GDPC1 or A191RL1Q225SBEA (GDP QoQ SAAR), CPIAUCSL, PAYEMS; yields DGS3MO, DGS2, DGS10, DGS30, T10Y2Y | Free api key; nightly fetch |
| Econ release calendar | FRED releases/dates | fred/releases/dates | Nightly |
| Crypto prices | CoinGecko /simple/price | ids: bitcoin,ethereum | Free, no key; 15-min fetch, cache aggressively |
| Industry benchmarks | Damodaran NYU datasets | Static links per industry on company pages | Link out only, with attribution |
Rules that apply everywhere:
- One shared HTTP client module with per-provider rate limiters, exponential backoff on 429/5xx, and a hard timeout.
- Cache every raw API response to disk (data/cache/) with a timestamp before parsing, so parser bugs never require re-fetching.
- Every stored datapoint keeps a source and fetched_at. Every page footer shows "data as of" timestamps.
## 7. Database schema (SQLAlchemy models; SQLite v1)
- companies: cik (pk), ticker (unique), name, gics_sector, gics_sub_industry, ir_url, active
- statement_facts: id, cik, statement (IS/BS/CF), canonical_item, fiscal_year, period_end, value, unit, xbrl_tag_used, form, filed_date, fetched_at. Unique on (cik, canonical_item, fiscal_year)
- ratios: id, cik, fiscal_year, ratio_key, value (nullable), na_reason (nullable), computed_at. Unique on (cik, ratio_key, fiscal_year)
- filings: id, cik, form, filed_date, period_of_report, accession, primary_doc_url
- prices: ticker (pk), price, change_abs, change_pct, as_of
- price_history: ticker, date, close (daily close only, for later sparklines; populate from the nightly quote)
- news: id (provider id, pk), ticker, published_at, headline, source, url, fetched_at
- watchlist: ticker (pk), added_at, news_alerts (bool), earnings_alerts (bool)
- notes: id, cik, content (markdown text), created_at, updated_at. Owner-authored research notes. NO job, migration, or refresh may ever modify or delete rows in this table; deletion happens only through the explicit UI action in 9.9
- earnings_calendar: ticker, event_date, when (bmo/amc/unknown), eps_estimate, confirmed, fetched_at
- econ_observations: series_id, obs_date, value. Unique on (series_id, obs_date)
- econ_releases: release_name, release_date
- alerts_log: id, kind (news/earnings), ticker, ref_id, sent_at (dedupe so nothing alerts twice)
- job_runs: job_name, started_at, finished_at, status, message (visibility into the schedulers)
## 8. Refresh cadence
| Job | Schedule | Scope |
|---|---|---|
| statements_refresh | Nightly 02:00 CT, and event-driven: when the nightly filings check sees a new 10-K/10-Q for a company, refresh that company | companyfacts pull -> canonical mapping -> ratio recompute |
| filings_refresh | Nightly 02:30 CT | submissions JSON -> filings table |
| universe_prices | Nightly 03:00 CT | one quote per S&P 500 ticker, throttled; also appends price_history |
| earnings_calendar | Nightly 03:30 CT | next 30 days |
| macro_refresh | Nightly 04:00 CT | FRED series + release calendar |
| watchlist_refresh | Hourly on the hour, 07:00-19:00 CT weekdays | quotes + news for watchlist tickers only (cap watchlist at 100 tickers; enforce in UI) |
| crypto_and_yields_strip | Hourly, same window | CoinGecko simple price; yields come from the nightly FRED pull (FRED is daily data; do not poll it hourly) |
| alert_check | Hourly, immediately after watchlist_refresh | Section 11 |
Page requests read from the DB only. Two allowed exceptions, both non-blocking with a DB fallback: (a) the open company page may trigger a background quote+news refresh for that one ticker if its data is older than 1 hour; (b) manual "refresh now" button on the watchlist and on any company page (per-ticker, throttled to one manual refresh per ticker per 5 minutes).
## 9. Pages and features
### 9.1 Home / search
- Search bar: matches ticker prefix and company-name substring, case-insensitive, against the companies table. Instant results via /api/search?q=. Keyboard navigable.
- Sector browse: list of GICS sectors; clicking one lists its companies alphabetically with ticker, name, latest price, daily change.
- Watchlist summary strip at top: ticker, price, day change, next earnings date.
### 9.2 Company page: /company/{ticker}
- Header: name, ticker, sector / sub-industry, delayed price + day change + as-of time, watchlist toggle (top right) with per-company alert switches (news, earnings).
- Description block (Phase 1: placeholder from seed or Wikipedia summary REST API fetched nightly and cached; Phase 5 replaces this - see Section 13).
- Comparables row: peer tickers from peers.json, each linking to its company page.
- Links row: Latest 10-K, Prior 10-K (direct EDGAR document links), Investor Relations (if ir_url present), All filings (filings tab), Damodaran industry dataset for its industry.
- Buttons/tabs: Financials, Ratios, News, Filings, Notes (with a count badge when notes exist).
### 9.3 Financials tab
- Three statements, each a dense table.
- Columns, left to right: FY(newest), %ch, FY-1, %ch, FY-2, %ch, FY-3, %ch, FY-4. Newest on the left (matches the owner's modeling convention).
- Percent change = (newer - older) / abs(older); render "-" when the older value is 0 or missing. Negative-to-positive flips will produce large magnitudes; render them anyway.
- Values in millions USD with thousands separators; negative in parentheses.
- Each row shows the canonical line item; tooltip (title attr) shows the XBRL tag actually used and the source form/filed date.
- Statement layouts are the canonical item lists in Section 10.1, in that order, skipping rows that are entirely null for that company.
### 9.4 Ratios tab
- Category index (Liquidity, Activity, Profitability, DuPont, Leverage, Cash Flow, Valuation-Equity, Valuation-Enterprise, Shareholder Return, Per Share, Growth).
- Clicking a category lists its ratios: name, formula, this company's latest-FY value, 5yr mini-history (values for each FY).
- Clicking a ratio opens the comps view: one table, rows = this company + its peers, columns = ratio value per company (latest FY), plus each company's 5yr values beneath. Same layout spirit as a sell-side comp sheet.
- Every ratio page shows the newbie description, "generally better when" direction, and caveats from ratios.yml.
- N/A handling: if a ratio is null, show "n/a" with its na_reason (e.g., "negative average equity - buybacks", "no inventory - not meaningful for this business", "negative FCF - multiple not meaningful").
### 9.5 News tab
- Reverse-chronological headlines for the ticker from the news table: timestamp, source, headline linking out. No article ingestion or summarization in v1.
### 9.6 Filings tab
- Table from filings: form, filed date, period, link. Filter chips: 10-K, 10-Q, 8-K, DEF 14A, Form 4, All.
### 9.7 Macro page
- Big three: latest GDP QoQ SAAR, CPI YoY, payrolls (latest month + 3-month average), each with value, prior value, and as-of date.
- Economy indicator per Section 10.4, with its rule printed on the page.
- Treasury strip: 3M, 2Y, 10Y, 30Y yields and the 10Y-2Y spread.
- Crypto strip: BTC and ETH prices only. No descriptions, no charts, per owner request.
- Econ calendar: next 14 days of FRED release dates, flagging CPI, Employment Situation, and GDP releases.
### 9.8 Watchlist page
- Table: ticker, name, price, day change, next earnings (date + bmo/amc), alert toggles, remove.
- Cap 100 tickers with a visible counter (generous; rate budget is comfortable at hourly cadence).
### 9.9 Notes (per company)
- A Notes tab on every company page: the owner's own research notes for that company, persisted forever until explicitly deleted.
- Multiple notes per company, newest first. Each note: markdown textarea, autosave on pause (debounced ~2s) plus an explicit Save button, created/updated timestamps displayed.
- Delete requires a confirm step. There is no bulk delete and no expiry. Notes are never touched by any scheduled job, data refresh, or universe change; if a company is removed from the seed file, its notes remain readable at its URL.
- Render markdown on display (headings, bold, lists, links). No external editor libraries; a plain textarea is fine.
- /api/notes/export returns all notes as one markdown file (grouped by company) so the owner can back up his own writing with one click. Mention the SQLite file path in CLAUDE.md as the thing to back up.
## 10. Computation specs
### 10.1 Canonical line items and XBRL tag fallback chains
Build pipelines/xbrl_map.py as an ordered-fallback mapper: for each canonical item, try tags in order, take the first present for that fiscal year; record xbrl_tag_used. Log every company/item with no match to a report the owner can review. Parsing rules for companyfacts:
- Use us-gaap facts, unit USD (shares for share counts, USD/shares for EPS).
- Annual values only: form == "10-K" and fp == "FY"; match fiscal_year from the fact's fy field and period_end from end.
- Duration facts (IS/CF) must span roughly a full year (330-400 days between start and end) to exclude quarterly stubs.
- Restatements: when the same (item, fiscal_year) appears in multiple filings, keep the most recently filed value.
- Fiscal years are company fiscal years (Oracle's FY2026 ends May 2026); label columns FY2026 etc., with period_end shown in the column tooltip.
Income statement (display order): revenue [RevenueFromContractWithCustomerExcludingAssessedTax, RevenueFromContractWithCustomerIncludingAssessedTax, Revenues, SalesRevenueNet]; cost_of_revenue [CostOfRevenue, CostOfGoodsAndServicesSold, CostOfGoodsSold]; gross_profit [GrossProfit, else revenue - cost_of_revenue]; rd_expense [ResearchAndDevelopmentExpense]; sga_expense [SellingGeneralAndAdministrativeExpense, GeneralAndAdministrativeExpense]; operating_income [OperatingIncomeLoss]; interest_expense [InterestExpense, InterestExpenseNonoperating, InterestIncomeExpenseNet]; pretax_income [IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest, IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments]; income_tax_expense [IncomeTaxExpenseBenefit]; net_income [NetIncomeLoss]; eps_diluted [EarningsPerShareDiluted]; shares_diluted [WeightedAverageNumberOfDilutedSharesOutstanding].
Balance sheet: cash [CashAndCashEquivalentsAtCarryingValue]; st_investments [ShortTermInvestments, MarketableSecuritiesCurrent, AvailableForSaleSecuritiesDebtSecuritiesCurrent]; accounts_receivable [AccountsReceivableNetCurrent, ReceivablesNetCurrent]; inventory [InventoryNet]; current_assets [AssetsCurrent]; ppe_net [PropertyPlantAndEquipmentNet]; goodwill [Goodwill]; intangibles [IntangibleAssetsNetExcludingGoodwill, FiniteLivedIntangibleAssetsNet]; total_assets [Assets]; accounts_payable [AccountsPayableCurrent, AccountsPayableAndAccruedLiabilitiesCurrent]; deferred_revenue_current [ContractWithCustomerLiabilityCurrent, DeferredRevenueCurrent]; short_term_debt [DebtCurrent, LongTermDebtCurrent, NotesPayableCurrent, ShortTermBorrowings - sum LongTermDebtCurrent + ShortTermBorrowings when DebtCurrent absent and both exist]; current_liabilities [LiabilitiesCurrent]; long_term_debt [LongTermDebtNoncurrent, LongTermDebt]; total_liabilities [Liabilities]; total_equity [StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest, StockholdersEquity].
Cash flow: cfo [NetCashProvidedByUsedInOperatingActivities, NetCashProvidedByUsedInOperatingActivitiesContinuingOperations]; d_and_a [DepreciationDepletionAndAmortization, DepreciationAmortizationAndAccretionNet, DepreciationAndAmortization]; stock_comp [ShareBasedCompensation]; capex [PaymentsToAcquirePropertyPlantAndEquipment, PaymentsToAcquireProductiveAssets]; cfi [NetCashProvidedByUsedInInvestingActivities]; dividends_paid [PaymentsOfDividends, PaymentsOfDividendsCommonStock]; buybacks [PaymentsForRepurchaseOfCommonStock]; debt_issued [ProceedsFromIssuanceOfLongTermDebt]; debt_repaid [RepaymentsOfLongTermDebt]; cff [NetCashProvidedByUsedInFinancingActivities].
Derived (compute after mapping, store like facts): ebit = operating_income; ebitda = operating_income + d_and_a (document as an approximation); total_debt = short_term_debt + long_term_debt; net_debt = total_debt - cash - st_investments; effective_tax_rate = income_tax_expense / pretax_income (null if pretax <= 0); nopat = ebit * (1 - effective_tax_rate); invested_capital = total_debt + total_equity - cash - st_investments; fcf = cfo - capex; working_capital = current_assets - current_liabilities; averages (avg_assets, avg_equity, avg_ar, avg_inventory, avg_ap, avg_ic) = mean of current and prior FY balance, current-year value when prior missing.
### 10.2 Ratio engine
Compute for every company and FY where inputs exist; otherwise store null + na_reason. Denominator <= 0 on equity-based ratios -> null with reason "non-positive average equity". Missing/zero inventory -> inventory ratios null "no inventory". EV-based multiples with non-positive denominators -> null "non-positive denominator".
Fiscal-data ratios: current_ratio ca/cl; quick_ratio (ca - inventory)/cl; cash_ratio (cash + st_investments)/cl; ocf_ratio cfo/cl; working_capital; asset_turnover revenue/avg_assets; fixed_asset_turnover revenue/avg ppe; inventory_turnover cost_of_revenue/avg_inventory; dio 365/inventory_turnover; receivables_turnover revenue/avg_ar; dso 365/receivables_turnover; payables_turnover cost_of_revenue/avg_ap; dpo 365/payables_turnover; ccc dio + dso - dpo; gross_margin; operating_margin; ebitda_margin; pretax_margin; net_margin; fcf_margin fcf/revenue; roa ni/avg_assets; roe ni/avg_equity; roic nopat/avg_ic; tax_burden ni/pretax; interest_burden pretax/ebit; equity_multiplier avg_assets/avg_equity; debt_to_equity total_debt/total_equity; debt_to_assets; net_debt_to_ebitda; interest_coverage ebit/interest_expense; ebitda_coverage ebitda/interest_expense; capex_to_sales; capex_to_da capex/d_and_a; accruals_ratio (ni - cfo)/avg_assets; cash_conversion cfo/ni; payout_ratio dividends_paid/ni; retention 1 - payout; sgr roe * retention; dividend_coverage fcf/dividends_paid; bvps total_equity/shares_diluted; revenue_per_share; fcf_per_share; revenue_yoy; ni_yoy; revenue_cagr_5y; rule_of_40 revenue_yoy + fcf_margin (label as SaaS-oriented).
Market-data ratios (compute at request time from latest price + latest-FY fundamentals; label "price as of" + "fundamentals FY20XX"): market_cap price * shares_diluted; ev market_cap + total_debt - cash - st_investments; pe price/eps_diluted; ps market_cap/revenue; pb market_cap/total_equity; p_fcf market_cap/fcf; earnings_yield; fcf_yield; ev_ebitda; ev_ebit; ev_sales; ev_fcf; ev_ic; ev_ebitda_less_capex ev/(ebitda - capex); buyback_yield buybacks/market_cap; shareholder_yield (dividends_paid + buybacks)/market_cap; peg pe/(ni_yoy * 100) null unless ni_yoy > 0.
### 10.3 ratios.yml content file
One entry per ratio: key, display_name, category, formula_display, better_when (higher/lower/depends), description (2-4 plain-English sentences for a newbie: what it shows, rough good/bad context, when it misleads), caveats list. Claude Code fills key/display_name/category/formula_display/better_when and leaves description as "TODO(owner)" - the owner writes every description himself, deliberately. Render TODOs as "description coming soon."
### 10.4 Economy indicator (exact rule, print it on the page)
Score three components -1/0/+1: CPI YoY now vs 3 months ago (rising > 0.2pp -> +1 heating, falling > 0.2pp -> -1, else 0); payrolls 3-month average monthly gain (> 180k -> +1, < 80k -> -1, else 0); GDP QoQ SAAR (> 3.0% -> +1, < 1.0% -> -1, else 0). Sum >= 2 HEATING, <= -2 COOLING, else STABLE. Display each component's value, score, and as-of date, plus the label: "Rules-based toy indicator using three series. Not a forecast."
## 11. Alerts
- Delivery: email via SMTP (env-configured; Gmail app password works). One module, alerts.py.
- News alerts (per watchlist ticker, toggleable): on each alert_check, new news rows since last check whose headline matches the keyword filter -> one digest email per run (not per article). Default keywords (config-editable): earnings, guidance, outlook, acquisition, acquire, merger, downgrade, upgrade, investigation, SEC, subpoena, resign, CEO, CFO, dividend, buyback, repurchase, restructuring, layoffs, bankruptcy, default. Log to alerts_log for dedupe.
- Earnings alerts (per ticker, toggleable): email at T-7 days, T-1 day, and day-of (morning), from earnings_calendar. Dedupe via alerts_log.
- All alert sends wrapped so failures log but never crash a job.
## 12. Phases and acceptance criteria
Phase 1 (build now): seed universe; EDGAR pipelines (companyfacts + submissions); canonical mapping; 5yr statements; ratio engine for all fiscal-data ratios; ratios.yml scaffold; pages 9.1 (search + sector browse, no prices), 9.2 (no live price; description placeholder), 9.3, 9.4 (fiscal ratios + comps view), 9.6, 9.9 (notes); peers.json seeded by GICS sub-industry (each company's 4 largest sub-industry siblings by revenue). ACCEPT: fresh clone + .env + one command -> browse to /company/ORCL and see 5 fiscal years of all three statements with % changes matching the 10-K, ratios with correct n/a reasons (ROE n/a for negative-equity years), working comps table vs MSFT/IBM/CRM, working 10-K links; create, edit, and delete a note on ORCL, and the note survives an app restart and a full statements_refresh run; tag-mapping coverage report shows < 10% missing on core items across the universe.
Phase 2: prices + news pipelines, watchlist (no alerts), market-data ratios, sector pages with prices, home strip.
Phase 3: earnings calendar, alert engine, watchlist alert toggles.
Phase 4: macro page complete (FRED, indicator, calendar, yields, crypto strip).
Phase 5: LLM company descriptions - fetch latest 10-K Item 1, summarize to a structured description (what it does, how it makes money, segments, key products/services, market position) via the Anthropic API, cache in DB, regenerate on new 10-K. Feature-flagged; site must run without an Anthropic key. Get current API usage/model details from https://docs.claude.com before implementing.
## 13. Out of scope - do not build
Auth/user accounts; real-time/streaming quotes; charting beyond simple sparklines; article scraping or full-text news; transcript ingestion (link out only); portfolio tracking or P&L; buy/sell signals or recommendations; mobile app; any Yahoo Finance usage; paying data sources.
## 14. Config (.env.example)
SEC_USER_AGENT="Joshua Lacroix Joshua.lacroix8b@gmail.com" (SEC requires a real contact); FINNHUB_API_KEY; FRED_API_KEY; SMTP_HOST; SMTP_PORT; SMTP_USER; SMTP_PASS; ALERT_EMAIL_TO; ANTHROPIC_API_KEY (Phase 5 only, optional); TZ="America/Chicago".
## 15. Standards and tests
- Type hints everywhere; ruff for lint/format.
- Required tests: xbrl_map fallback selection and annual-duration filtering against 2-3 saved companyfacts fixtures (include ORCL); ratio engine golden tests - hand-computed expected values for ORCL FY2026 and one normal-equity company (ROE null path for ORCL, DSO, ROIC, current/quick/cash ratios, EV math with a stubbed price); percent-change edge cases (zero, null, sign flip); alert dedupe; notes persistence (note rows untouched after statements_refresh and filings_refresh run against the same company).
- Every scheduled job writes job_runs; a /status page lists last run + status per job.
- Graceful degradation: any missing datapoint renders as "-" or "n/a", never a 500.
## 16. Legal and etiquette
SEC fair-access policy: honor rate limits and User-Agent, cache aggressively, link to documents rather than mirroring. Attribute Damodaran data on any page linking it. Finnhub/FRED/CoinGecko: free tiers, personal use, keys in env only, never committed. This is a personal research tool, not investment advice; put that line in the footer.
## 17. Open items for the owner (do not block Phase 1)
1. Fill ir_url in sp500.csv over time.
2. Write ratios.yml descriptions (deliberately reserved for the owner).
3. Review the auto-seeded peers.json and hand-tune peer sets, starting with ORCL: [MSFT, IBM, CRM, SAP].
4. Get free API keys: Finnhub, FRED. Set up a Gmail app password for alerts (Phase 3).
5. Pick a name for the site header.
