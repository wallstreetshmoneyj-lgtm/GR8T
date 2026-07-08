# Trend identification quality — five trend definitions vs a random-walk null (no trading)

*Run date: 2026-07-08. Pure state scoring — no entries, exits, costs, or P&L. Data: same committed Yahoo snapshot as the Donchian study (crypto daily = max history; futures daily = ~7y **front-month continuous, whose roll gaps fire fake trend flips — back-adjusted contracts are needed for firm futures conclusions**; 4h resampled from 1h, ~2y cap; weekly resampled from daily). Null = stationary block bootstrap of each instrument's own bars (1000 resamples, mean block 5 bars) preserving the return distribution, volatility clustering and per-bar OHLC geometry while destroying multi-week serial dependence; short (≤~1 week) dependence survives in the null, which makes it slightly conservative. p-values are one-sided empirical: P(null ≥ real). Stars: \*\*\* p<0.01, \*\* p<0.05, \* p<0.10.*

## 1. Sample sizes

| Group | TF | Instrument | Start | End | Bars | Bars/yr |
|---|---|---|---|---|---|---|
| crypto | 1d | ADA-USD | 2017-11-09 | 2026-07-06 | 3162 | 365 |
| crypto | 1d | AVAX-USD | 2020-07-13 | 2026-07-06 | 2116 | 354 |
| crypto | 1d | BNB-USD | 2017-11-09 | 2026-07-06 | 3162 | 365 |
| crypto | 1d | BTC-USD | 2014-09-17 | 2026-07-06 | 4311 | 365 |
| crypto | 1d | DOGE-USD | 2017-11-09 | 2026-07-06 | 3162 | 365 |
| crypto | 1d | DOT-USD | 2020-08-20 | 2026-07-06 | 2147 | 365 |
| crypto | 1d | ETH-USD | 2017-11-09 | 2026-07-06 | 3162 | 365 |
| crypto | 1d | LINK-USD | 2017-11-09 | 2026-07-06 | 3162 | 365 |
| crypto | 1d | SOL-USD | 2020-04-10 | 2026-07-06 | 2279 | 365 |
| crypto | 1d | XRP-USD | 2017-11-09 | 2026-07-06 | 3162 | 365 |
| futures | 1d | CL=F | 2019-07-08 | 2026-07-06 | 1760 | 251 |
| futures | 1d | ES=F | 2019-07-08 | 2026-07-06 | 1761 | 252 |
| futures | 1d | GC=F | 2019-07-08 | 2026-07-06 | 1760 | 251 |
| futures | 1d | HG=F | 2019-07-08 | 2026-07-06 | 1761 | 252 |
| futures | 1d | NG=F | 2019-07-08 | 2026-07-06 | 1761 | 252 |
| futures | 1d | NQ=F | 2019-07-08 | 2026-07-06 | 1761 | 252 |
| futures | 1d | SI=F | 2019-07-08 | 2026-07-06 | 1760 | 251 |
| futures | 1d | YM=F | 2019-07-08 | 2026-07-06 | 1761 | 252 |
| futures | 1d | ZB=F | 2019-07-08 | 2026-07-06 | 1761 | 252 |
| futures | 1d | ZN=F | 2019-07-08 | 2026-07-06 | 1761 | 252 |
| crypto | 1w | ADA-USD | 2017-11-12 | 2026-07-12 | 453 | 52 |
| crypto | 1w | AVAX-USD | 2020-07-19 | 2026-07-12 | 304 | 51 |
| crypto | 1w | BNB-USD | 2017-11-12 | 2026-07-12 | 453 | 52 |
| crypto | 1w | BTC-USD | 2014-09-21 | 2026-07-12 | 617 | 52 |
| crypto | 1w | DOGE-USD | 2017-11-12 | 2026-07-12 | 453 | 52 |
| crypto | 1w | DOT-USD | 2020-08-23 | 2026-07-12 | 308 | 52 |
| crypto | 1w | ETH-USD | 2017-11-12 | 2026-07-12 | 453 | 52 |
| crypto | 1w | LINK-USD | 2017-11-12 | 2026-07-12 | 453 | 52 |
| crypto | 1w | SOL-USD | 2020-04-12 | 2026-07-12 | 327 | 52 |
| crypto | 1w | XRP-USD | 2017-11-12 | 2026-07-12 | 453 | 52 |
| futures | 1w | CL=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| futures | 1w | ES=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| futures | 1w | GC=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| futures | 1w | HG=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| futures | 1w | NG=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| futures | 1w | NQ=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| futures | 1w | SI=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| futures | 1w | YM=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| futures | 1w | ZB=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| futures | 1w | ZN=F | 2019-07-14 | 2026-07-12 | 366 | 52 |
| crypto | 4h | BTC-USD | 2024-07-08 | 2026-07-07 | 4372 | 2188 |
| crypto | 4h | ETH-USD | 2024-07-08 | 2026-07-07 | 4372 | 2188 |
| futures | 4h | ES=F | 2024-02-12 | 2026-07-07 | 3712 | 1547 |
| futures | 4h | GC=F | 2024-02-12 | 2026-07-07 | 3720 | 1550 |
| futures | 4h | NQ=F | 2024-02-12 | 2026-07-07 | 3709 | 1545 |

## 2. Does the market trend at all? (indicator-free gates)

Lo–MacKinlay variance ratios (VR>1 = persistent, <1 = mean-reverting) with heteroskedasticity-robust z-stats, and R/S Hurst (H>0.5 = persistent). Verdict rule: ≥2 lags significantly persistent (z>1.645) and more persistent than anti-persistent lags → TRENDING; mirror image → MEAN-REVERTING; else RANDOM-WALK-like.

### 1d

| Group | Instrument | VR(2) | VR(5) | VR(10) | VR(20) | VR(40) | Hurst | Verdict |
|---|---|---|---|---|---|---|---|---|
| crypto | ADA-USD | 0.98 | 1.14 | 1.22* | 1.40** | 1.60*** | 0.62 | TRENDING |
| crypto | AVAX-USD | 1.00 | 1.09 | 1.22** | 1.36** | 1.66*** | 0.61 | TRENDING |
| crypto | BNB-USD | 0.99 | 1.05 | 1.07 | 1.28 | 1.49** | 0.60 | RANDOM-WALK |
| crypto | BTC-USD | 0.98 | 0.99 | 1.03 | 1.09 | 1.20 | 0.60 | RANDOM-WALK |
| crypto | DOGE-USD | 1.02 | 1.08 | 1.14 | 1.24 | 1.35 | 0.60 | RANDOM-WALK |
| crypto | DOT-USD | 0.97 | 0.96 | 0.90 | 0.95 | 1.12 | 0.58 | RANDOM-WALK |
| crypto | ETH-USD | 0.96 | 1.02 | 1.08 | 1.15 | 1.26 | 0.60 | RANDOM-WALK |
| crypto | LINK-USD | 0.95* | 0.97 | 0.99 | 1.03 | 1.05 | 0.53 | RANDOM-WALK |
| crypto | SOL-USD | 0.95 | 0.98 | 1.03 | 1.17 | 1.47** | 0.61 | RANDOM-WALK |
| crypto | XRP-USD | 0.99 | 1.05 | 1.18* | 1.31** | 1.32 | 0.58 | TRENDING |
| futures | CL=F | 1.03 | 0.93 | 0.96 | 1.14 | 1.26 | 0.57 | RANDOM-WALK |
| futures | ES=F | 0.85** | 0.82 | 0.80 | 0.82 | 0.73 | 0.56 | RANDOM-WALK |
| futures | GC=F | 0.98 | 0.92 | 0.81 | 0.76 | 0.76 | 0.56 | RANDOM-WALK |
| futures | HG=F | 0.95 | 0.95 | 0.91 | 0.82 | 0.75 | 0.54 | RANDOM-WALK |
| futures | NG=F | 0.90** | 0.88 | 0.77 | 0.72 | 0.71 | 0.53 | RANDOM-WALK |
| futures | NQ=F | 0.87*** | 0.81* | 0.77 | 0.79 | 0.74 | 0.57 | MEAN-REVERTING |
| futures | SI=F | 0.95 | 0.95 | 0.85 | 0.79 | 0.79 | 0.58 | RANDOM-WALK |
| futures | YM=F | 0.84** | 0.85 | 0.84 | 0.85 | 0.73 | 0.54 | RANDOM-WALK |
| futures | ZB=F | 1.01 | 0.93 | 0.92 | 0.95 | 0.98 | 0.56 | RANDOM-WALK |
| futures | ZN=F | 1.00 | 0.91 | 0.88 | 0.91 | 0.97 | 0.56 | RANDOM-WALK |

### 1w

| Group | Instrument | VR(2) | VR(5) | VR(10) | VR(20) | VR(40) | Hurst | Verdict |
|---|---|---|---|---|---|---|---|---|
| crypto | ADA-USD | 1.02 | 1.33 | 1.11 | 1.09 | 1.27 | 0.67 | RANDOM-WALK |
| crypto | AVAX-USD | 1.19** | 1.38** | 1.62** | 1.57* | — | 0.65 | TRENDING |
| crypto | BNB-USD | 1.12 | 1.32 | 1.27 | 1.38 | 1.31 | 0.66 | RANDOM-WALK |
| crypto | BTC-USD | 1.06 | 1.18 | 1.29* | 1.50** | 1.69** | 0.66 | TRENDING |
| crypto | DOGE-USD | 1.13 | 1.26 | 1.17 | 1.36 | 1.51 | 0.64 | RANDOM-WALK |
| crypto | DOT-USD | 0.96 | 1.06 | 1.27 | 1.35 | — | 0.59 | RANDOM-WALK |
| crypto | ETH-USD | 1.09** | 1.19* | 1.14 | 1.24 | 1.48 | 0.65 | TRENDING |
| crypto | LINK-USD | 1.04 | 1.08 | 0.89 | 0.83 | 0.87 | 0.56 | RANDOM-WALK |
| crypto | SOL-USD | 1.10* | 1.41*** | 1.71*** | 1.87*** | — | 0.67 | TRENDING |
| crypto | XRP-USD | 1.12 | 1.22 | 0.81 | 0.63 | 0.67 | 0.60 | RANDOM-WALK |
| futures | CL=F | 1.11 | 1.18 | 1.26 | 0.98 | — | 0.60 | RANDOM-WALK |
| futures | ES=F | 0.92 | 0.96 | 0.82 | 0.67 | — | 0.60 | RANDOM-WALK |
| futures | GC=F | 0.91 | 0.83 | 0.85 | 0.89 | — | 0.59 | RANDOM-WALK |
| futures | HG=F | 0.95 | 0.82 | 0.75 | 0.72 | — | 0.61 | RANDOM-WALK |
| futures | NG=F | 0.97 | 0.91 | 0.88 | 0.92 | — | 0.58 | RANDOM-WALK |
| futures | NQ=F | 0.93 | 0.98 | 0.90 | 0.80 | — | 0.63 | RANDOM-WALK |
| futures | SI=F | 0.94 | 0.84 | 0.88 | 0.88 | — | 0.58 | RANDOM-WALK |
| futures | YM=F | 0.94 | 0.95 | 0.79 | 0.62 | — | 0.56 | RANDOM-WALK |
| futures | ZB=F | 0.97 | 1.04 | 1.03 | 0.91 | — | 0.59 | RANDOM-WALK |
| futures | ZN=F | 0.93 | 0.99 | 1.05 | 1.04 | — | 0.61 | RANDOM-WALK |

### 4h

| Group | Instrument | VR(2) | VR(5) | VR(10) | VR(20) | VR(40) | Hurst | Verdict |
|---|---|---|---|---|---|---|---|---|
| crypto | BTC-USD | 0.99 | 0.98 | 0.92 | 0.93 | 0.91 | 0.56 | RANDOM-WALK |
| crypto | ETH-USD | 1.02 | 1.05 | 1.01 | 1.04 | 1.03 | 0.57 | RANDOM-WALK |
| futures | ES=F | 1.02 | 1.04 | 0.88 | 0.89 | 0.80 | 0.56 | RANDOM-WALK |
| futures | GC=F | 1.01 | 1.03 | 1.04 | 0.98 | 0.94 | 0.56 | RANDOM-WALK |
| futures | NQ=F | 1.02 | 1.04 | 0.91 | 0.90 | 0.82 | 0.57 | RANDOM-WALK |

Verdict counts: 1d/crypto: RANDOM-WALK×7, TRENDING×3; 1d/futures: RANDOM-WALK×9, MEAN-REVERTING×1; 1w/crypto: RANDOM-WALK×6, TRENDING×4; 1w/futures: RANDOM-WALK×10; 4h/crypto: RANDOM-WALK×2; 4h/futures: RANDOM-WALK×3.

## 3. Method vs its random-walk null (medians across instruments)

`capture` = signed segment move / segment absolute path length (chop sits near 0). z = (real − null mean)/null std, medians across the block's instruments. `beats null` = instruments where ≥2 of {duration, hit rate, capture} have p<0.05 against the null.

### crypto — 1d

| Method | Capture (real) | Capture (null) | z cap | z dur | z hit | Flips/yr | Med dur (bars) | Beats null | Composite z |
|---|---|---|---|---|---|---|---|---|---|
| sma10_40 | -0.11 | -0.16 | 1.50 | 0.71 | 1.09 | 10.29 | 30.50 | 1/10 | 1.10 |
| sma50 | 0.03 | 0.04 | -0.15 | 1.17 | 0.62 | 20.59 | 5.00 | 1/10 | 0.55 |
| swing5 | -0.04 | -0.07 | 0.63 | 0.52 | 0.46 | 8.03 | 37.00 | 2/10 | 0.54 |
| donch20 | -0.06 | -0.07 | 0.39 | 0.88 | 0.22 | 7.58 | 37.25 | 0/10 | 0.50 |
| donch55 | -0.06 | -0.06 | 0.04 | 0.44 | 0.67 | 2.88 | 85.50 | 1/10 | 0.38 |
| tsmom120 | -0.02 | -0.01 | -0.07 | 0.16 | 1.04 | 10.63 | 4.00 | 2/10 | 0.37 |
| tsmom60 | 0.01 | -0.00 | 0.26 | -0.07 | 0.58 | 18.21 | 4.00 | 0/10 | 0.26 |
| tsmom20 | 0.01 | 0.03 | -0.30 | -0.37 | 0.33 | 35.79 | 3.25 | 0/10 | -0.11 |

### crypto — 1w

| Method | Capture (real) | Capture (null) | z cap | z dur | z hit | Flips/yr | Med dur (bars) | Beats null | Composite z |
|---|---|---|---|---|---|---|---|---|---|
| tsmom20 | 0.04 | 0.02 | 0.19 | -0.04 | 0.34 | 3.91 | 6.50 | 0/10 | 0.16 |
| sma50 | 0.05 | 0.04 | -0.07 | -0.12 | 0.46 | 2.84 | 5.00 | 0/10 | 0.09 |
| tsmom60 | 0.03 | -0.01 | 0.23 | -0.17 | 0.00 | 2.46 | 5.50 | 0/10 | 0.02 |
| sma10_40 | -0.15 | -0.18 | 0.34 | -0.53 | 0.17 | 1.76 | 22.00 | 0/10 | -0.01 |
| donch55 | -0.07 | -0.09 | 0.09 | -0.37 | -0.11 | 0.62 | 80.25 | 0/10 | -0.13 |
| tsmom120 | -0.12 | -0.03 | -0.37 | -0.28 | -0.32 | 1.66 | 5.00 | 0/10 | -0.32 |
| donch20 | -0.12 | -0.07 | -0.37 | -0.38 | -0.47 | 1.25 | 26.25 | 1/10 | -0.41 |
| swing5 | -0.08 | -0.08 | -0.08 | -0.74 | -0.48 | 1.42 | 26.50 | 0/10 | -0.44 |

### crypto — 4h

| Method | Capture (real) | Capture (null) | z cap | z dur | z hit | Flips/yr | Med dur (bars) | Beats null | Composite z |
|---|---|---|---|---|---|---|---|---|---|
| tsmom120 | 0.05 | -0.01 | 1.11 | -0.88 | 0.11 | 97.54 | 4.00 | 0/2 | 0.11 |
| swing5 | -0.07 | -0.08 | 0.04 | 0.52 | -0.28 | 50.69 | 33.50 | 0/2 | 0.09 |
| donch55 | -0.06 | -0.07 | 0.24 | -0.13 | -0.39 | 20.86 | 77.25 | 0/2 | -0.09 |
| donch20 | -0.07 | -0.07 | 0.02 | 0.01 | -0.86 | 50.00 | 33.50 | 0/2 | -0.28 |
| tsmom60 | -0.03 | -0.00 | -0.70 | -0.33 | 0.07 | 121.81 | 3.75 | 0/2 | -0.32 |
| sma50 | 0.03 | 0.04 | -0.23 | -0.87 | -0.83 | 162.00 | 4.00 | 0/2 | -0.64 |
| sma10_40 | -0.18 | -0.17 | -0.54 | -1.24 | -0.72 | 74.75 | 23.50 | 0/2 | -0.83 |
| tsmom20 | -0.00 | 0.02 | -0.72 | -0.72 | -1.47 | 221.26 | 4.00 | 0/2 | -0.97 |

### futures — 1d

| Method | Capture (real) | Capture (null) | z cap | z dur | z hit | Flips/yr | Med dur (bars) | Beats null | Composite z |
|---|---|---|---|---|---|---|---|---|---|
| donch20 | -0.06 | -0.08 | 0.62 | 0.46 | 0.40 | 5.71 | 30.00 | 0/10 | 0.49 |
| sma50 | 0.04 | 0.06 | -0.25 | 0.23 | 0.55 | 17.56 | 4.00 | 1/10 | 0.18 |
| tsmom20 | 0.05 | 0.03 | 0.42 | 0.06 | 0.03 | 25.29 | 4.00 | 0/10 | 0.17 |
| tsmom60 | -0.00 | 0.01 | -0.09 | -0.05 | 0.55 | 13.68 | 4.50 | 1/10 | 0.13 |
| tsmom120 | 0.02 | 0.00 | 0.17 | -0.38 | 0.60 | 10.58 | 3.75 | 0/10 | 0.13 |
| sma10_40 | -0.17 | -0.17 | -0.17 | -0.02 | 0.21 | 7.52 | 26.00 | 0/10 | 0.01 |
| donch55 | -0.09 | -0.07 | -0.26 | -0.50 | 0.13 | 2.62 | 69.75 | 0/10 | -0.21 |
| swing5 | -0.12 | -0.09 | -0.68 | -0.22 | -0.03 | 6.15 | 26.50 | 0/10 | -0.31 |

### futures — 1w

| Method | Capture (real) | Capture (null) | z cap | z dur | z hit | Flips/yr | Med dur (bars) | Beats null | Composite z |
|---|---|---|---|---|---|---|---|---|---|
| donch55 | 0.01 | -0.09 | 0.65 | -0.10 | 0.12 | 0.34 | 93.50 | 0/10 | 0.23 |
| tsmom120 | 0.13 | -0.02 | 0.68 | -0.31 | -0.06 | 1.27 | 4.75 | 0/10 | 0.10 |
| swing5 | -0.07 | -0.10 | 0.22 | -0.27 | 0.01 | 1.21 | 32.00 | 0/10 | -0.01 |
| sma10_40 | -0.15 | -0.17 | 0.10 | -0.20 | 0.07 | 1.68 | 21.50 | 0/10 | -0.01 |
| sma50 | 0.02 | 0.05 | -0.27 | -0.32 | 0.05 | 3.95 | 3.00 | 0/10 | -0.18 |
| tsmom60 | -0.05 | 0.00 | -0.17 | -0.28 | -0.37 | 2.81 | 4.25 | 0/10 | -0.27 |
| donch20 | -0.09 | -0.09 | -0.18 | -0.32 | -0.37 | 1.09 | 31.00 | 0/10 | -0.29 |
| tsmom20 | -0.05 | 0.03 | -0.50 | -0.15 | -0.40 | 4.98 | 4.00 | 0/10 | -0.35 |

### futures — 4h

| Method | Capture (real) | Capture (null) | z cap | z dur | z hit | Flips/yr | Med dur (bars) | Beats null | Composite z |
|---|---|---|---|---|---|---|---|---|---|
| tsmom120 | 0.07 | 0.01 | 1.24 | 0.02 | 0.83 | 51.67 | 4.00 | 0/3 | 0.70 |
| sma10_40 | -0.15 | -0.17 | 0.69 | 1.04 | 0.05 | 42.95 | 27.00 | 1/3 | 0.59 |
| swing5 | -0.06 | -0.06 | 0.17 | 1.13 | 0.18 | 33.58 | 36.00 | 0/3 | 0.50 |
| tsmom60 | -0.00 | 0.02 | -0.45 | -0.16 | 0.81 | 79.62 | 4.00 | 0/3 | 0.06 |
| donch20 | -0.05 | -0.06 | 0.24 | 0.22 | -0.36 | 31.09 | 39.50 | 0/3 | 0.03 |
| tsmom20 | 0.03 | 0.04 | -0.33 | 0.11 | 0.15 | 138.25 | 4.00 | 0/3 | -0.02 |
| donch55 | -0.08 | -0.07 | -0.23 | -0.31 | 0.44 | 14.50 | 91.50 | 0/3 | -0.03 |
| sma50 | 0.01 | 0.08 | -1.08 | -0.12 | 0.28 | 99.23 | 5.00 | 0/3 | -0.31 |

## 4. Method ranking (composite z vs null, across all blocks)

| Config | Family | Median composite z | Med z capture | Med z duration | Med z hit | Σ beats null | Σ series |
|---|---|---|---|---|---|---|---|
| tsmom120 | TS momentum | 0.12 | 0.43 | -0.30 | 0.35 | 2 | 45 |
| swing5 | Swing structure | 0.04 | 0.11 | 0.15 | -0.01 | 2 | 45 |
| tsmom60 | TS momentum | 0.04 | -0.13 | -0.17 | 0.31 | 1 | 45 |
| sma10_40 | 10/40 crossover | 0.00 | 0.22 | -0.11 | 0.12 | 2 | 45 |
| sma50 | 50-SMA state | -0.05 | -0.24 | -0.12 | 0.37 | 2 | 45 |
| donch55 | Donchian | -0.06 | 0.07 | -0.22 | 0.13 | 1 | 45 |
| tsmom20 | TS momentum | -0.07 | -0.32 | -0.10 | 0.09 | 0 | 45 |
| donch20 | Donchian | -0.12 | 0.13 | 0.12 | -0.36 | 1 | 45 |

Family ranking (median of member configs):

| Family | Median composite z | Σ beats null | Σ series |
|---|---|---|---|
| Swing structure | 0.04 | 2 | 45 |
| TS momentum | 0.04 | 3 | 135 |
| 10/40 crossover | 0.00 | 2 | 45 |
| 50-SMA state | -0.05 | 2 | 45 |
| Donchian | -0.09 | 2 | 90 |

## 5. Timeframe comparison (median composite z across methods)

| Group | TF | Median composite z | Best method | Best composite z | Share beating null |
|---|---|---|---|---|---|
| crypto | 1d | 0.44 | sma10_40 | 1.10 | 0.09 |
| crypto | 1w | -0.07 | tsmom20 | 0.16 | 0.01 |
| crypto | 4h | -0.30 | tsmom120 | 0.11 | 0.00 |
| futures | 1d | 0.13 | donch20 | 0.49 | 0.03 |
| futures | 1w | -0.10 | donch55 | 0.23 | 0.00 |
| futures | 4h | 0.05 | tsmom120 | 0.70 | 0.04 |

Caveats: 4h = only ~2 years and 2–3 instruments per group; weekly futures = ~365 bars (thin for slow methods like tsmom120).

## 6. How long do trends last? (best method per block)

| Group | TF | Best method | p25 (bars) | Median | Mean | p75 | Median ≈days | Null mean dur |
|---|---|---|---|---|---|---|---|---|
| crypto | 1d | sma10_40 | 15.5 | 30.5 | 34.8 | 47.5 | 30.5 | 32.7 |
| crypto | 1w | tsmom20 | 1.9 | 6.5 | 12.0 | 17.5 | 45.7 | 11.9 |
| crypto | 4h | tsmom120 | 1.0 | 4.0 | 22.4 | 13.9 | 0.7 | 27.0 |
| futures | 1d | donch20 | 19.9 | 30.0 | 43.2 | 56.8 | 43.5 | 41.2 |
| futures | 1w | donch55 | 85.5 | 93.5 | 93.5 | 93.8 | 656.7 | 100.7 |
| futures | 4h | tsmom120 | 2.0 | 4.0 | 29.9 | 22.0 | 0.9 | 29.5 |

(Median across instruments of the per-instrument duration stats; completed segments only — the final, right-censored run of each series is excluded.)

## 7. Plain-English answers

**Q1 — Do these markets trend at all (indicator-free)?**
- crypto 1d: RANDOM-WALK 7/10, TRENDING 3/10; median Hurst 0.60.
- futures 1d: RANDOM-WALK 9/10, MEAN-REVERTING 1/10; median Hurst 0.56.
- crypto 1w: RANDOM-WALK 6/10, TRENDING 4/10; median Hurst 0.65.
- futures 1w: RANDOM-WALK 10/10; median Hurst 0.60.
- crypto 4h: RANDOM-WALK 2/2; median Hurst 0.57.
- futures 4h: RANDOM-WALK 3/3; median Hurst 0.56.

**Q2 — Which definition identifies real (above-null) trend?** Config ranking by median composite z across all blocks: tsmom120 (0.12), swing5 (0.04), tsmom60 (0.04), sma10_40 (0.00), sma50 (-0.05), donch55 (-0.06), tsmom20 (-0.07), donch20 (-0.12).
- Series where a method beats its null (≥2 of 3 metrics p<0.05), out of 45 series per method: tsmom120: 2, swing5: 2, tsmom60: 1, sma10_40: 2, sma50: 2, donch55: 1, tsmom20: 0, donch20: 1.

**Q3 — Which timeframe is trend most identifiable on?** Median composite z: 1d: 0.22, 4h: -0.03, 1w: -0.07. (4h rests on ~2y and 5 instruments; weekly on ~7–12y but few bars.)

**Q4 — Crypto vs futures?** Median composite z — crypto: 0.01, futures: 0.02; share of series×methods beating the null — crypto: 5%, futures: 2%. Futures verdicts carry the roll-gap caveat.

**Q5 — How long do real trends last?** See section 6: median completed-trend duration for the best method per block, in bars and approximate calendar days. Downstream POI/entry logic must operate inside those windows.

**Q6 — Methods identifying noise rather than trend:** donch20 (2% of series beat null), donch55 (2% of series beat null), sma10_40 (4% of series beat null), sma50 (4% of series beat null), swing5 (4% of series beat null), tsmom120 (4% of series beat null), tsmom20 (0% of series beat null), tsmom60 (2% of series beat null). Any method whose persistence and capture sit inside its null band is reading structure into randomness — its 'trends' would appear identically on shuffled data.

**Bottom line.** The indicator-free gates and the method-vs-null scores tell one consistent story with an uncomfortable punchline. The markets are not pure random walks everywhere: crypto shows genuinely elevated variance ratios at 10–40-bar horizons on daily and weekly bars (every crypto VR(40) > 1 on daily; 3–4 of 10 instruments individually significant; median Hurst 0.60–0.65), while futures lean the other way (VR < 1, i.e. mean-reversion, with the roll-gap caveat). But NONE of the five binary state definitions converts that weak persistence into identification that reliably clears its own shuffled-data null: the best block is sma10_40 on crypto 1d (composite z ≈ 1.10), and across all 45 series × 8 configs only a handful beat the null at p<0.05 — about what false positives alone would produce. Flip counts, duration distributions and capture ratios of every method look like what the same method generates on block-shuffled returns. Read together: the exploitable signal, to the extent it exists, lives in crypto at the 20–40 trading-day horizon and is weak — a property of the market, faintly visible to variance ratios, but too faint for any of these binary trend states to certify segment by segment. Downstream logic should treat 'trend state' as a weak prior (crypto daily, ~1-month horizon), not as a validated regime label; and futures conclusions need back-adjusted contracts before trusting anything here.

---
*Reproduce: `python score_trends.py` (add `--fast` for 200 resamples). Full metrics incl. null means/percentiles/p-values: `output/method_metrics.csv`; market gates: `output/market_viability.csv`.*