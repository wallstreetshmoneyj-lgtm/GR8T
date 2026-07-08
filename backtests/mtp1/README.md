# MTP-1 — Micro Trend Portfolio v1 (research-grade backtest)

Diversified, volatility-sized, long/short Donchian-breakout trend following
with a chandelier ATR trailing stop, on 17 yfinance continuous futures
(16 with ≥10y history in the headline stats; RTY=F reported separately).
Built to find out whether the edge is real, not to look good:

- **Zero look-ahead, asserted twice**: hand-recomputed Donchian channels at
  random samples, and sampled executed trades re-derived from raw arrays
  (signal bar breakout condition, next-bar-open fill, fill price). A third,
  out-of-script check hand-traced a full trade's chandelier trail and
  gap-stop exit and matched the engine exactly.
- **No optimization**: the headline is the MEDIAN of the 15-combo grid
  (N ∈ {20,35,50,75,100} × K ∈ {2,3,4}), never the best.
- **Random-entry bootstrap null** (1,000 sims, seed 42): identical exit
  engine, sizing, caps, and costs; entries at random dates matched to the
  strategy's per-market trade and direction counts.
- **Pass A** (fractional contracts) measures the edge; **Pass B** (integer
  micro contracts + ~10% notional margin check on $10K) measures what
  survives a small account. Six explicit pass/fail gates (G1–G6).

**Data caveat (printed in the report too):** yfinance `=F` series are
front-month chains with roll gaps, not back-adjusted — Donchian/ATR see
roll artifacts. Approximation only; final validation on IBKR back-adjusted
data.

**Contract specs:** SIL and MHG verified against CME contract specs. The
task sheet's MHG line ($1,250/pt, ~$0.63/tick) is off by 2× — CME MHG is
2,500 lbs → $2,500/pt, $1.25/tick. Verified values are used.

## Files

- `mtp1_backtest.py` — single script, CONFIG dict at top
- `data/*_1d_raw.csv.gz` — committed raw OHLC snapshots (auto_adjust=False)
- `output/report.txt` — full console report incl. gate verdicts
- `output/grid_results.csv`, `per_market.csv`, `trades.csv`,
  `correlations.csv`, `equity_curve.png`, `bootstrap_hist.png`

## Run

```bash
.venv/bin/python mtp1_backtest.py           # full run
.venv/bin/python mtp1_backtest.py --smoke   # 2 combos, 25 bootstraps
```
