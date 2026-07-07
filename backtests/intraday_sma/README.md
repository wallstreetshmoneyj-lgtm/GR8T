# Intraday SMA entry-rule backtest (exploratory)

Head-to-head test of two always-in-market long/short entry rules —
**50-period SMA price-cross** vs **10/40 SMA crossover** — on **1h** and
**4h** bars, for **crypto** (10 -USD spot pairs) and **futures** (10 =F
front-month continuous) separately. Gross and net of costs, fixed ±1 and
volatility-scaled sizing, 70/30 in-sample/out-of-sample split, and
deflated-Sharpe multiple-testing accounting.

**Read this first:** Yahoo caps hourly history at ~730 days, so the entire
study rests on ≈2 years of data. Treat everything as exploratory. Futures
tickers are front-month continuous with roll gaps, which distorts their
results.

## Files

- `backtest.py` — the full pipeline (download → signals → backtest → report)
- `data/*.csv.gz` — cached 1h close snapshots (committed for reproducibility)
- `output/SUMMARY.md` — paste-ready markdown report with the verdict
- `output/results_all_configs.csv` — every config × {FULL, IS, OOS}

## Run

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python backtest.py            # re-download (results will drift with new data)
.venv/bin/python backtest.py --cached   # reproduce exactly from the committed snapshot
```

Note: in this repo's remote environment, outbound TLS goes through a
re-terminating proxy; `backtest.py` points `curl_cffi` at the proxy CA
bundle automatically when present (`/root/.ccr/ca-bundle.crt`) and uses
`chrome110` impersonation, which both the proxy and Yahoo accept.
