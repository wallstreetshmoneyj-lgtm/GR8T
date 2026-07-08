# Trend identification quality — no trading, methods vs random-walk null

Scores five trend-DEFINITION methods purely as per-bar state generators
(+1/−1) — no entries, exits, costs, or P&L — and asks one question: which
method identifies real, persistent trend, on which asset class, on which
timeframe?

Methods: 50-SMA state, 10/40 SMA crossover state, Donchian breakout state
(N ∈ {20, 55}), time-series momentum state (L ∈ {20, 60, 120}), and swing
structure (k=5 fractal, confirmed k bars later, market-structure-break
flips). Timeframes: daily (primary), weekly (resampled), 4h cross-check
(BTC/ETH/ES/NQ/GC).

**The core control:** every metric (flip frequency, duration distribution,
next-bar hit rate, forward return, segment capture efficiency) is compared
against a stationary block bootstrap (1000 resamples, mean block 5 bars) of
the instrument's own bars — same return distribution, volatility
clustering, and per-bar OHLC geometry, but multi-week serial dependence
destroyed. Indicator-free gates: Lo–MacKinlay variance ratios (robust z)
at lags {2,5,10,20,40} and R/S Hurst.

**Headline (see `output/SUMMARY.md`):** crypto shows weak but real
persistence at 10–40-bar horizons on daily/weekly bars (all crypto daily
VR(40) > 1, median Hurst 0.60–0.65); futures lean mean-reverting. Yet no
binary state definition reliably beats its shuffled-data null — flip
counts, durations, and capture of every method look like what the same
indicator produces on randomness. Trend state should be treated as a weak
prior (crypto, ~1-month horizon), not a validated regime label.

## Files

- `score_trends.py` — the full pipeline (states → metrics → null → report)
- `output/SUMMARY.md` — paste-ready report
- `output/method_metrics.csv` — all method×instrument×timeframe metrics
  with null means/percentiles, z-scores, p-values
- `output/market_viability.csv` — VR/Hurst/verdict per instrument×timeframe

Data: reuses the committed OHLC snapshots in `../donchian_regime/data/`
(same snapshot across studies; futures are front-month continuous with
roll gaps — flagged throughout).

## Run

```bash
.venv/bin/python score_trends.py          # 1000 resamples, ~4 min, seeded
.venv/bin/python score_trends.py --fast   # 200 resamples smoke test
```
