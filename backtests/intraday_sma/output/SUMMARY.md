# Intraday SMA entry-rule backtest — 50-SMA cross vs 10/40 crossover (1h & 4h, crypto vs futures)

*Run date: 2026-07-07. Data: Yahoo Finance via yfinance. **Exploratory** — Yahoo caps hourly history at ~730 days, so every result below rests on ≈2 years of data (see sample sizes). 4h bars are **resampled from 1h**, anchored to UTC midnight (Yahoo's native 4h has the same lookback; resampling keeps one consistent data source for both groups). Futures are front-month continuous with roll gaps, which distorts their results — a proper futures test needs back-adjusted contracts. Costs: 20 bp round-trip crypto, 2 bp futures, charged per unit of turnover. Signals on closed bars, entry next bar. Long/short, always in market.*

## 1. Sample sizes (actual data retrieved)

| Group | Instrument | History starts | 1h bars | 4h bars |
|---|---|---|---|---|
| crypto | ADA-USD | 2024-07-08 | 17479 | 4372 |
| crypto | AVAX-USD | 2024-07-08 | 17479 | 4372 |
| crypto | BNB-USD | 2024-07-08 | 17482 | 4372 |
| crypto | BTC-USD | 2024-07-08 | 17482 | 4372 |
| crypto | DOGE-USD | 2024-07-08 | 17480 | 4372 |
| crypto | DOT-USD | 2024-07-08 | 17481 | 4372 |
| crypto | ETH-USD | 2024-07-08 | 17479 | 4372 |
| crypto | LINK-USD | 2024-07-08 | 17479 | 4372 |
| crypto | SOL-USD | 2024-07-08 | 17481 | 4372 |
| crypto | XRP-USD | 2024-07-08 | 17482 | 4372 |
| futures | CL=F | 2024-02-12 | 13513 | 3682 |
| futures | ES=F | 2024-02-12 | 13693 | 3712 |
| futures | GC=F | 2024-02-12 | 13733 | 3720 |
| futures | HG=F | 2024-02-12 | 13727 | 3720 |
| futures | NG=F | 2024-02-12 | 13499 | 3676 |
| futures | NQ=F | 2024-02-12 | 13690 | 3709 |
| futures | SI=F | 2024-02-12 | 13730 | 3720 |
| futures | YM=F | 2024-02-12 | 13686 | 3710 |
| futures | ZB=F | 2024-02-12 | 13653 | 3695 |
| futures | ZN=F | 2024-02-12 | 13655 | 3695 |

No instruments were skipped — all 20 delivered enough history for a 50-period signal plus IS/OOS evaluation.

## 2. Group × timeframe × strategy — equal-weight portfolio Sharpe (FULL sample)

### Sizing: fixed

| Group | TF | Strategy | Gross Sharpe | Net Sharpe | Net ann. ret | Max DD | Trades/yr | Turnover/yr |
|---|---|---|---|---|---|---|---|---|
| crypto | 1h | Buy & hold | 0.15 | 0.15 | 0.10 | -0.73 | — | 0.00 |
| crypto | 1h | 10/40 SMA cross | 0.74 | -0.23 | -0.13 | -0.78 | 288.28 | 553.90 |
| crypto | 1h | 50-SMA cross | 0.91 | -1.28 | -0.73 | -0.89 | 637.62 | 1254.94 |
| crypto | 4h | Buy & hold | 0.14 | 0.14 | 0.09 | -0.73 | — | 0.00 |
| crypto | 4h | 10/40 SMA cross | 0.21 | -0.03 | -0.02 | -0.70 | 71.58 | 139.46 |
| crypto | 4h | 50-SMA cross | 0.77 | 0.25 | 0.14 | -0.58 | 165.19 | 294.14 |
| futures | 1h | Buy & hold | 1.55 | 1.55 | 0.23 | -0.12 | — | 0.00 |
| futures | 1h | 10/40 SMA cross | -0.11 | -0.35 | -0.05 | -0.25 | 263.75 | 346.13 |
| futures | 1h | 50-SMA cross | -1.03 | -1.59 | -0.22 | -0.43 | 539.58 | 777.66 |
| futures | 4h | Buy & hold | 1.52 | 1.52 | 0.22 | -0.12 | — | 0.00 |
| futures | 4h | 10/40 SMA cross | -0.15 | -0.22 | -0.03 | -0.16 | 74.59 | 96.46 |
| futures | 4h | 50-SMA cross | 0.36 | 0.22 | 0.03 | -0.17 | 132.50 | 200.50 |

### Sizing: volscaled

| Group | TF | Strategy | Gross Sharpe | Net Sharpe | Net ann. ret | Max DD | Trades/yr | Turnover/yr |
|---|---|---|---|---|---|---|---|---|
| crypto | 1h | Buy & hold | 0.15 | 0.15 | 0.10 | -0.73 | — | 0.00 |
| crypto | 1h | 10/40 SMA cross | 1.32 | 0.08 | 0.01 | -0.23 | 285.28 | 143.93 |
| crypto | 1h | 50-SMA cross | 1.66 | -0.99 | -0.12 | -0.31 | 636.12 | 312.54 |
| crypto | 4h | Buy & hold | 0.14 | 0.14 | 0.09 | -0.73 | — | 0.00 |
| crypto | 4h | 10/40 SMA cross | 0.57 | 0.18 | 0.02 | -0.17 | 75.59 | 45.94 |
| crypto | 4h | 50-SMA cross | 1.36 | 0.64 | 0.08 | -0.15 | 160.68 | 85.38 |
| futures | 1h | Buy & hold | 1.55 | 1.55 | 0.23 | -0.12 | — | 0.00 |
| futures | 1h | 10/40 SMA cross | 0.10 | -0.42 | -0.03 | -0.10 | 247.50 | 380.81 |
| futures | 1h | 50-SMA cross | -0.28 | -1.43 | -0.10 | -0.23 | 506.66 | 834.03 |
| futures | 4h | Buy & hold | 1.52 | 1.52 | 0.22 | -0.12 | — | 0.00 |
| futures | 4h | 10/40 SMA cross | 0.05 | -0.13 | -0.01 | -0.14 | 79.59 | 131.31 |
| futures | 4h | 50-SMA cross | 0.54 | 0.21 | 0.02 | -0.14 | 145.01 | 247.00 |

## 3. Per-instrument results, ranked by net Sharpe (FULL sample, fixed ±1 sizing)

Flag = CONSISTENT if net Sharpe > 0 in *both* the IS (oldest 70%) and OOS (newest 30%) sub-periods, else FRAGILE.

### crypto — 1h

| Instrument | Strategy | Gross SR | Net SR | t-stat | Win rate | Profit factor | Trades/yr | Flag |
|---|---|---|---|---|---|---|---|---|
| DOGE-USD | 10/40 SMA cross | 1.28 | 0.67 | 0.95 | 0.33 | 1.15 | 276.27 | FRAGILE |
| XRP-USD | 10/40 SMA cross | 1.26 | 0.61 | 0.87 | 0.33 | 1.14 | 275.27 | FRAGILE |
| AVAX-USD | 10/40 SMA cross | 0.71 | 0.07 | 0.09 | 0.35 | 1.01 | 278.77 | FRAGILE |
| ETH-USD | 10/40 SMA cross | 0.76 | -0.09 | -0.13 | 0.33 | 0.98 | 289.78 | FRAGILE |
| XRP-USD | 50-SMA cross | 1.28 | -0.26 | -0.36 | 0.16 | 0.96 | 653.63 | FRAGILE |
| LINK-USD | 10/40 SMA cross | 0.34 | -0.29 | -0.41 | 0.31 | 0.95 | 274.27 | FRAGILE |
| DOT-USD | 10/40 SMA cross | 0.24 | -0.38 | -0.54 | 0.32 | 0.93 | 268.26 | FRAGILE |
| ADA-USD | 10/40 SMA cross | 0.21 | -0.41 | -0.58 | 0.32 | 0.93 | 287.28 | FRAGILE |
| DOT-USD | 50-SMA cross | 0.95 | -0.45 | -0.63 | 0.19 | 0.93 | 600.08 | FRAGILE |
| SOL-USD | 50-SMA cross | 1.01 | -0.47 | -0.67 | 0.19 | 0.93 | 593.08 | FRAGILE |
| SOL-USD | 10/40 SMA cross | 0.17 | -0.51 | -0.72 | 0.34 | 0.91 | 271.76 | FRAGILE |
| DOGE-USD | 50-SMA cross | 0.85 | -0.54 | -0.76 | 0.19 | 0.92 | 626.11 | FRAGILE |
| BNB-USD | 10/40 SMA cross | 0.46 | -0.57 | -0.81 | 0.32 | 0.89 | 275.27 | FRAGILE |
| ADA-USD | 50-SMA cross | 0.77 | -0.59 | -0.83 | 0.18 | 0.91 | 632.61 | FRAGILE |
| AVAX-USD | 50-SMA cross | 0.33 | -1.15 | -1.62 | 0.18 | 0.84 | 642.62 | FRAGILE |
| ETH-USD | 50-SMA cross | 0.52 | -1.31 | -1.85 | 0.18 | 0.82 | 622.10 | FRAGILE |
| LINK-USD | 50-SMA cross | 0.02 | -1.44 | -2.03 | 0.17 | 0.81 | 634.62 | FRAGILE |
| BTC-USD | 10/40 SMA cross | -0.50 | -1.67 | -2.35 | 0.30 | 0.73 | 274.77 | FRAGILE |
| BTC-USD | 50-SMA cross | 0.61 | -1.93 | -2.73 | 0.17 | 0.74 | 598.08 | FRAGILE |
| BNB-USD | 50-SMA cross | 0.11 | -2.41 | -3.41 | 0.16 | 0.68 | 674.15 | FRAGILE |

### crypto — 4h

| Instrument | Strategy | Gross SR | Net SR | t-stat | Win rate | Profit factor | Trades/yr | Flag |
|---|---|---|---|---|---|---|---|---|
| DOT-USD | 50-SMA cross | 1.28 | 0.98 | 1.38 | 0.23 | 1.40 | 126.64 | CONSISTENT |
| XRP-USD | 50-SMA cross | 1.22 | 0.87 | 1.23 | 0.23 | 1.39 | 143.66 | FRAGILE |
| ADA-USD | 10/40 SMA cross | 0.85 | 0.70 | 0.98 | 0.33 | 1.32 | 71.58 | CONSISTENT |
| DOGE-USD | 10/40 SMA cross | 0.76 | 0.62 | 0.87 | 0.36 | 1.29 | 65.57 | FRAGILE |
| ADA-USD | 50-SMA cross | 0.79 | 0.47 | 0.67 | 0.19 | 1.17 | 144.66 | FRAGILE |
| DOGE-USD | 50-SMA cross | 0.69 | 0.36 | 0.51 | 0.20 | 1.12 | 146.17 | FRAGILE |
| XRP-USD | 10/40 SMA cross | 0.52 | 0.35 | 0.49 | 0.34 | 1.14 | 71.58 | FRAGILE |
| SOL-USD | 10/40 SMA cross | 0.42 | 0.25 | 0.35 | 0.37 | 1.10 | 68.58 | FRAGILE |
| SOL-USD | 50-SMA cross | 0.59 | 0.20 | 0.29 | 0.20 | 1.07 | 150.67 | FRAGILE |
| LINK-USD | 50-SMA cross | 0.46 | 0.13 | 0.19 | 0.22 | 1.05 | 141.66 | FRAGILE |
| BNB-USD | 50-SMA cross | 0.39 | -0.14 | -0.19 | 0.24 | 0.95 | 137.66 | FRAGILE |
| ETH-USD | 10/40 SMA cross | 0.06 | -0.15 | -0.22 | 0.34 | 0.95 | 72.58 | FRAGILE |
| DOT-USD | 10/40 SMA cross | -0.12 | -0.27 | -0.38 | 0.32 | 0.90 | 63.57 | FRAGILE |
| LINK-USD | 10/40 SMA cross | -0.18 | -0.33 | -0.47 | 0.32 | 0.87 | 69.58 | FRAGILE |
| ETH-USD | 50-SMA cross | 0.07 | -0.44 | -0.62 | 0.17 | 0.88 | 171.70 | FRAGILE |
| BNB-USD | 10/40 SMA cross | -0.20 | -0.47 | -0.67 | 0.36 | 0.84 | 71.58 | FRAGILE |
| AVAX-USD | 50-SMA cross | -0.18 | -0.55 | -0.78 | 0.18 | 0.84 | 160.68 | FRAGILE |
| AVAX-USD | 10/40 SMA cross | -0.56 | -0.72 | -1.02 | 0.30 | 0.76 | 68.58 | FRAGILE |
| BTC-USD | 50-SMA cross | -0.07 | -0.72 | -1.02 | 0.22 | 0.79 | 149.67 | FRAGILE |
| BTC-USD | 10/40 SMA cross | -0.42 | -0.75 | -1.06 | 0.31 | 0.77 | 76.59 | FRAGILE |

### futures — 1h

| Instrument | Strategy | Gross SR | Net SR | t-stat | Win rate | Profit factor | Trades/yr | Flag |
|---|---|---|---|---|---|---|---|---|
| GC=F | 10/40 SMA cross | 1.21 | 1.06 | 1.64 | 0.37 | 1.30 | 167.92 | CONSISTENT |
| SI=F | 10/40 SMA cross | 0.94 | 0.86 | 1.34 | 0.34 | 1.25 | 184.58 | FRAGILE |
| GC=F | 50-SMA cross | 0.82 | 0.45 | 0.69 | 0.19 | 1.09 | 413.75 | FRAGILE |
| SI=F | 50-SMA cross | 0.53 | 0.36 | 0.56 | 0.19 | 1.08 | 408.75 | FRAGILE |
| HG=F | 10/40 SMA cross | 0.21 | 0.09 | 0.14 | 0.33 | 1.02 | 180.00 | FRAGILE |
| ZN=F | 10/40 SMA cross | 0.53 | -0.08 | -0.12 | 0.34 | 0.98 | 168.75 | FRAGILE |
| CL=F | 10/40 SMA cross | -0.03 | -0.11 | -0.17 | 0.33 | 0.97 | 172.08 | FRAGILE |
| CL=F | 50-SMA cross | 0.05 | -0.13 | -0.19 | 0.20 | 0.97 | 379.58 | FRAGILE |
| NQ=F | 50-SMA cross | 0.17 | -0.16 | -0.25 | 0.22 | 0.97 | 350.41 | FRAGILE |
| ZB=F | 10/40 SMA cross | 0.06 | -0.26 | -0.41 | 0.34 | 0.94 | 165.42 | FRAGILE |
| HG=F | 50-SMA cross | -0.16 | -0.43 | -0.66 | 0.19 | 0.91 | 411.25 | FRAGILE |
| NG=F | 10/40 SMA cross | -0.59 | -0.63 | -0.97 | 0.35 | 0.83 | 160.00 | FRAGILE |
| NQ=F | 10/40 SMA cross | -0.57 | -0.73 | -1.14 | 0.34 | 0.83 | 168.75 | FRAGILE |
| YM=F | 50-SMA cross | -0.34 | -0.82 | -1.27 | 0.20 | 0.84 | 363.75 | FRAGILE |
| ZB=F | 50-SMA cross | -0.27 | -1.03 | -1.60 | 0.19 | 0.82 | 390.41 | FRAGILE |
| ES=F | 50-SMA cross | -0.59 | -1.04 | -1.62 | 0.20 | 0.80 | 372.50 | FRAGILE |
| YM=F | 10/40 SMA cross | -0.90 | -1.13 | -1.75 | 0.31 | 0.76 | 177.50 | FRAGILE |
| ES=F | 10/40 SMA cross | -1.40 | -1.62 | -2.50 | 0.33 | 0.67 | 174.58 | FRAGILE |
| NG=F | 50-SMA cross | -2.10 | -2.20 | -3.40 | 0.20 | 0.64 | 371.66 | FRAGILE |
| ZN=F | 50-SMA cross | -0.96 | -2.39 | -3.70 | 0.17 | 0.63 | 400.41 | FRAGILE |

### futures — 4h

| Instrument | Strategy | Gross SR | Net SR | t-stat | Win rate | Profit factor | Trades/yr | Flag |
|---|---|---|---|---|---|---|---|---|
| GC=F | 10/40 SMA cross | 1.11 | 1.07 | 1.65 | 0.44 | 1.81 | 42.08 | CONSISTENT |
| SI=F | 50-SMA cross | 0.96 | 0.92 | 1.42 | 0.26 | 1.50 | 95.84 | CONSISTENT |
| GC=F | 50-SMA cross | 0.91 | 0.82 | 1.27 | 0.21 | 1.44 | 95.42 | CONSISTENT |
| CL=F | 50-SMA cross | 0.29 | 0.24 | 0.37 | 0.20 | 1.13 | 107.09 | FRAGILE |
| SI=F | 10/40 SMA cross | 0.16 | 0.14 | 0.21 | 0.36 | 1.07 | 51.25 | FRAGILE |
| NQ=F | 10/40 SMA cross | 0.16 | 0.12 | 0.19 | 0.35 | 1.06 | 42.92 | FRAGILE |
| HG=F | 10/40 SMA cross | 0.10 | 0.07 | 0.11 | 0.37 | 1.03 | 50.42 | FRAGILE |
| ES=F | 10/40 SMA cross | 0.12 | 0.07 | 0.10 | 0.36 | 1.04 | 43.33 | FRAGILE |
| NG=F | 50-SMA cross | 0.04 | 0.02 | 0.03 | 0.29 | 1.01 | 75.84 | FRAGILE |
| YM=F | 10/40 SMA cross | 0.05 | -0.01 | -0.01 | 0.34 | 1.00 | 47.08 | FRAGILE |
| NQ=F | 50-SMA cross | 0.06 | -0.04 | -0.06 | 0.18 | 0.99 | 98.34 | FRAGILE |
| YM=F | 50-SMA cross | -0.16 | -0.28 | -0.44 | 0.21 | 0.89 | 96.25 | FRAGILE |
| HG=F | 50-SMA cross | -0.25 | -0.33 | -0.51 | 0.18 | 0.88 | 113.75 | FRAGILE |
| NG=F | 10/40 SMA cross | -0.36 | -0.37 | -0.57 | 0.38 | 0.82 | 47.92 | FRAGILE |
| CL=F | 10/40 SMA cross | -0.49 | -0.51 | -0.79 | 0.32 | 0.76 | 52.50 | FRAGILE |
| ES=F | 50-SMA cross | -0.55 | -0.68 | -1.05 | 0.17 | 0.75 | 102.92 | FRAGILE |
| ZB=F | 50-SMA cross | -0.52 | -0.72 | -1.12 | 0.22 | 0.74 | 106.25 | FRAGILE |
| ZN=F | 10/40 SMA cross | -0.69 | -0.88 | -1.36 | 0.33 | 0.67 | 52.09 | FRAGILE |
| ZB=F | 10/40 SMA cross | -0.90 | -1.00 | -1.55 | 0.35 | 0.62 | 52.09 | FRAGILE |
| ZN=F | 50-SMA cross | -0.69 | -1.09 | -1.69 | 0.18 | 0.67 | 108.75 | FRAGILE |

## 4. Fixed ±1 vs volatility-scaled sizing (EW portfolios, net Sharpe, FULL sample)

| Group | TF | Strategy | Fixed net SR | Vol-scaled net SR | Δ (scaled − fixed) |
|---|---|---|---|---|---|
| crypto | 1h | 10/40 SMA cross | -0.23 | 0.08 | 0.32 |
| crypto | 1h | 50-SMA cross | -1.28 | -0.99 | 0.30 |
| crypto | 4h | 10/40 SMA cross | -0.03 | 0.18 | 0.21 |
| crypto | 4h | 50-SMA cross | 0.25 | 0.64 | 0.39 |
| futures | 1h | 10/40 SMA cross | -0.35 | -0.42 | -0.07 |
| futures | 1h | 50-SMA cross | -1.59 | -1.43 | 0.16 |
| futures | 4h | 10/40 SMA cross | -0.22 | -0.13 | 0.09 |
| futures | 4h | 50-SMA cross | 0.22 | 0.21 | -0.00 |

## 5. Out-of-sample validation (select on IS only, run once on OOS)

Oldest 70% in-sample / newest 30% out-of-sample; the better strategy per group × timeframe × sizing is picked on IS portfolio net Sharpe alone, then evaluated once on OOS. Degradation = OOS − IS.

| Group | TF | Sizing | Selected (on IS) | IS net SR | OOS net SR | Degradation | B&H OOS net SR |
|---|---|---|---|---|---|---|---|
| crypto | 1h | fixed | 10/40 SMA cross | 0.18 | -1.42 | -1.60 | -1.25 |
| crypto | 1h | volscaled | 10/40 SMA cross | 0.81 | -1.54 | -2.35 | -1.25 |
| crypto | 4h | fixed | 50-SMA cross | 0.54 | -0.63 | -1.17 | -1.45 |
| crypto | 4h | volscaled | 50-SMA cross | 1.11 | -0.45 | -1.56 | -1.45 |
| futures | 1h | fixed | 10/40 SMA cross | -0.87 | 0.47 | 1.34 | 1.27 |
| futures | 1h | volscaled | 10/40 SMA cross | -0.30 | -0.68 | -0.38 | 1.27 |
| futures | 4h | fixed | 50-SMA cross | 0.14 | 0.36 | 0.22 | 1.31 |
| futures | 4h | volscaled | 50-SMA cross | 0.65 | -0.68 | -1.32 | 1.31 |

## 6. Multiple-testing accounting

Total strategy configs evaluated (instrument- and portfolio-level, FULL sample): **N = 176**. Distribution of NET annualized Sharpes across all of them: mean -0.22, median -0.16, std 0.78, 5th pct -1.63, 95th pct 0.98.

Top configs — regular vs deflated Sharpe (Bailey & López de Prado; SR\* = expected max Sharpe of N zero-skill trials with the observed cross-config Sharpe variance):

| Config | Net ann. SR | SR* (exp. max, ann.) | P(true SR>0) | Deflated SR  P(SR>SR*) |
|---|---|---|---|---|
| futures 4h 10/40 SMA cross volscaled (GC=F) | 1.52 | 2.12 | 0.99 | 0.18 |
| futures 4h 50-SMA cross volscaled (SI=F) | 1.35 | 2.12 | 0.98 | 0.11 |
| futures 4h 50-SMA cross volscaled (GC=F) | 1.24 | 2.12 | 0.97 | 0.09 |
| futures 1h 10/40 SMA cross volscaled (GC=F) | 1.22 | 2.12 | 0.97 | 0.08 |
| crypto 4h 50-SMA cross volscaled (DOT-USD) | 1.09 | 2.12 | 0.94 | 0.07 |
| futures 4h 10/40 SMA cross fixed (GC=F) | 1.07 | 2.12 | 0.95 | 0.05 |

## 7. Plain-English verdict

**Q1 — 50-SMA cross vs 10/40 crossover:**
- crypto 1h: **10/40 SMA cross** wins on net Sharpe (-0.23 vs -1.28, fixed sizing, EW portfolio).
- crypto 4h: **50-SMA cross** wins on net Sharpe (0.25 vs -0.03, fixed sizing, EW portfolio).
- futures 1h: **10/40 SMA cross** wins on net Sharpe (-0.35 vs -1.59, fixed sizing, EW portfolio).
- futures 4h: **50-SMA cross** wins on net Sharpe (0.22 vs -0.22, fixed sizing, EW portfolio).

**Q2 — 1h vs 4h:** average EW-portfolio net Sharpe across strategies and sizings —
- crypto: 1h avg -0.60, 4h avg 0.26 → **4h** is less bad / better.
- futures: 1h avg -0.95, 4h avg 0.02 → **4h** is less bad / better.

**Q3 — crypto vs futures:** average net Sharpe across all intraday configs: crypto -0.17, futures -0.46 → **crypto** shows the cleaner (or less negative) trend edge at these horizons. Futures results carry the extra caveat of front-month roll gaps.

**Q4 — does anything survive costs + OOS + deflation, or beat buy-and-hold?**
- Positive OOS net Sharpe after IS-only selection: 2 of 8 selections.
- OOS net Sharpe above buy-and-hold OOS: 2 of 8 — but only 0 of those were also positive in absolute terms (beating a negative benchmark just means losing less).
- Positive OOS **and** above buy-and-hold: 0 of 8.
- Deflated Sharpe > 0.5 (i.e. more likely skill than the luck-of-the-draw expected max of 6 examined top configs): 0 of 6.
- Buy-and-hold EW-portfolio net Sharpe (FULL sample) for reference — crypto/1h: 0.15, crypto/4h: 0.14, futures/1h: 1.55, futures/4h: 1.52.

**Bottom line: nothing survives the full gauntlet.** No configuration is simultaneously positive out-of-sample, better than buy-and-hold, and distinguishable from selection luck (all deflated Sharpes are far below 0.5). On ~2 years of intraday data these two SMA entry rules do not demonstrate a deployable edge net of costs; slower signals on 4h bars merely lose less than fast ones on 1h, where costs are ruinous. This matches the prior daily-bar finding that raw entry rules carry little standalone value.

---
*Reproduce: `python backtest.py` (or `--cached` to reuse the committed data snapshot in `data/`). All configs: `output/results_all_configs.csv` (column `period` ∈ FULL/IS/OOS).*