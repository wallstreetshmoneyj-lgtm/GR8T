# Donchian breakout + 50-SMA regime filter — marginal-contribution study (daily, with 4h cross-check)

*Run date: 2026-07-07. Data: Yahoo via yfinance — crypto daily = max history (BTC from 2014, alts from 2017–2020), futures daily = ~7y **front-month continuous with roll gaps** (gaps fire false breakouts and distort these results; a proper futures test needs back-adjusted contracts), 4h = resampled from 1h (Yahoo caps intraday at ~730d). Signals on closed bars, entry next bar. Donchian channels use PRIOR N bars (current excluded). Costs 20bp/2bp round-trip charged per unit turnover; costs are reported but secondary here. Sizing below is vol-scaled (15% target, 3× cap) unless marked fixed. **Exploratory — honesty over impressive numbers.***

## 1. Sample sizes

| Group | TF | Instrument | Start | End | Bars | Bars/yr (empirical) |
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
| crypto | 4h | BTC-USD | 2024-07-08 | 2026-07-07 | 4372 | 2188 |
| crypto | 4h | ETH-USD | 2024-07-08 | 2026-07-07 | 4372 | 2188 |
| futures | 4h | ES=F | 2024-02-12 | 2026-07-07 | 3712 | 1547 |
| futures | 4h | GC=F | 2024-02-12 | 2026-07-07 | 3720 | 1550 |
| futures | 4h | NQ=F | 2024-02-12 | 2026-07-07 | 3709 | 1545 |

No instruments skipped.

## 2. Lookback sweep — EW-portfolio Sharpe by N (vol-scaled)

Rows are strategy × exit; columns are the entry lookback N (exit channel = N/2). B (50-SMA) and buy & hold have no N and are shown as single columns on the right of each block.

### NET Sharpe

**crypto — 1d**  (B 50-SMA: 1.42, buy & hold: 1.21)

| Strategy / exit | N=10 | N=20 | N=40 | N=55 | N=80 |
|---|---|---|---|---|---|
| A Donchian breakout / channel | 1.26 | 1.30 | 0.77 | 0.74 | 0.70 |
| A Donchian breakout / atr | 1.32 | 1.53 | 1.28 | 1.37 | 1.33 |
| C combo (A gated by B) / channel | 1.39 | 1.31 | 0.99 | 1.06 | 1.15 |
| C combo (A gated by B) / atr | 1.47 | 1.47 | 1.28 | 1.37 | 1.33 |
| D Donchian fade (diagnostic) / mid | -1.66 | -1.56 | -1.11 | -0.94 | -0.75 |

**crypto — 4h**  (B 50-SMA: -0.23, buy & hold: 0.16)

| Strategy / exit | N=10 | N=20 | N=40 | N=55 | N=80 |
|---|---|---|---|---|---|
| A Donchian breakout / channel | 0.66 | 0.30 | 0.53 | 0.19 | 0.40 |
| A Donchian breakout / atr | 0.85 | 0.38 | 0.88 | 0.59 | 0.76 |
| C combo (A gated by B) / channel | 0.25 | 0.17 | 0.59 | 0.15 | -0.02 |
| C combo (A gated by B) / atr | 0.58 | 0.25 | 0.87 | 0.59 | 0.77 |
| D Donchian fade (diagnostic) / mid | -1.95 | -1.26 | -1.12 | -0.68 | -0.54 |

**futures — 1d**  (B 50-SMA: 0.62, buy & hold: 0.51)

| Strategy / exit | N=10 | N=20 | N=40 | N=55 | N=80 |
|---|---|---|---|---|---|
| A Donchian breakout / channel | 0.03 | 0.12 | 0.47 | 0.29 | 0.28 |
| A Donchian breakout / atr | -0.09 | 0.23 | 0.38 | 0.30 | 0.32 |
| C combo (A gated by B) / channel | 0.23 | 0.28 | 0.52 | 0.41 | 0.45 |
| C combo (A gated by B) / atr | 0.24 | 0.38 | 0.43 | 0.33 | 0.36 |
| D Donchian fade (diagnostic) / mid | -0.31 | -0.29 | -0.58 | -0.60 | -0.45 |

**futures — 4h**  (B 50-SMA: 0.34, buy & hold: 1.55)

| Strategy / exit | N=10 | N=20 | N=40 | N=55 | N=80 |
|---|---|---|---|---|---|
| A Donchian breakout / channel | 0.42 | 0.65 | 0.33 | 0.21 | 0.31 |
| A Donchian breakout / atr | 0.44 | 0.47 | 0.26 | 0.41 | 0.66 |
| C combo (A gated by B) / channel | 0.20 | 0.60 | 0.21 | 0.27 | 0.49 |
| C combo (A gated by B) / atr | 0.21 | 0.36 | 0.15 | 0.33 | 0.61 |
| D Donchian fade (diagnostic) / mid | -0.68 | -0.63 | -0.65 | -0.32 | -0.45 |


### GROSS Sharpe

**crypto — 1d**  (B 50-SMA: 1.52, buy & hold: 1.21)

| Strategy / exit | N=10 | N=20 | N=40 | N=55 | N=80 |
|---|---|---|---|---|---|
| A Donchian breakout / channel | 1.36 | 1.36 | 0.82 | 0.78 | 0.74 |
| A Donchian breakout / atr | 1.41 | 1.60 | 1.33 | 1.41 | 1.37 |
| C combo (A gated by B) / channel | 1.49 | 1.38 | 1.05 | 1.11 | 1.20 |
| C combo (A gated by B) / atr | 1.57 | 1.55 | 1.33 | 1.42 | 1.37 |
| D Donchian fade (diagnostic) / mid | -1.55 | -1.49 | -1.06 | -0.89 | -0.72 |

**crypto — 4h**  (B 50-SMA: 0.56, buy & hold: 0.16)

| Strategy / exit | N=10 | N=20 | N=40 | N=55 | N=80 |
|---|---|---|---|---|---|
| A Donchian breakout / channel | 1.29 | 0.70 | 0.78 | 0.42 | 0.57 |
| A Donchian breakout / atr | 1.39 | 0.81 | 1.22 | 0.91 | 1.04 |
| C combo (A gated by B) / channel | 0.98 | 0.71 | 0.96 | 0.57 | 0.44 |
| C combo (A gated by B) / atr | 1.25 | 0.79 | 1.21 | 0.91 | 1.05 |
| D Donchian fade (diagnostic) / mid | -1.12 | -0.74 | -0.82 | -0.42 | -0.34 |

**futures — 1d**  (B 50-SMA: 0.68, buy & hold: 0.51)

| Strategy / exit | N=10 | N=20 | N=40 | N=55 | N=80 |
|---|---|---|---|---|---|
| A Donchian breakout / channel | 0.08 | 0.16 | 0.49 | 0.31 | 0.30 |
| A Donchian breakout / atr | -0.04 | 0.26 | 0.40 | 0.33 | 0.35 |
| C combo (A gated by B) / channel | 0.28 | 0.33 | 0.55 | 0.44 | 0.48 |
| C combo (A gated by B) / atr | 0.29 | 0.42 | 0.46 | 0.36 | 0.39 |
| D Donchian fade (diagnostic) / mid | -0.25 | -0.26 | -0.55 | -0.58 | -0.43 |

**futures — 4h**  (B 50-SMA: 0.53, buy & hold: 1.55)

| Strategy / exit | N=10 | N=20 | N=40 | N=55 | N=80 |
|---|---|---|---|---|---|
| A Donchian breakout / channel | 0.59 | 0.75 | 0.40 | 0.28 | 0.37 |
| A Donchian breakout / atr | 0.58 | 0.59 | 0.36 | 0.50 | 0.74 |
| C combo (A gated by B) / channel | 0.39 | 0.73 | 0.32 | 0.38 | 0.61 |
| C combo (A gated by B) / atr | 0.39 | 0.50 | 0.25 | 0.42 | 0.69 |
| D Donchian fade (diagnostic) / mid | -0.46 | -0.50 | -0.56 | -0.25 | -0.39 |

## 3. THE CENTRAL TEST — marginal contribution (A vs B vs C)

Channel exit, vol-scaled. 'A med' / 'C med' are medians across the five N values (medians avoid cherry-picking a lookback); B has no N. The verdict counts at how many of the 5 lookbacks C's net Sharpe beats BOTH A at the same N and B.

| Group | TF | Piece | Gross SR | Net SR | Max DD | Win rate | Payoff | Trades/yr | Turnover/yr |
|---|---|---|---|---|---|---|---|---|---|
| crypto | 1d | A Donchian (med across N) | 0.82 | 0.77 | -0.21 | 0.42 | 3.68 | 6.35 | 5.97 |
| crypto | 1d | B 50-SMA regime | 1.52 | 1.42 | -0.14 | 0.38 | 5.04 | 22.45 | 14.54 |
| crypto | 1d | C combo (med across N) | 1.20 | 1.15 | -0.15 | 0.37 | 4.71 | 10.84 | 7.02 |
| crypto | 4h | A Donchian (med across N) | 0.70 | 0.40 | -0.15 | 0.33 | 2.35 | 35.04 | 30.90 |
| crypto | 4h | B 50-SMA regime | 0.56 | -0.23 | -0.24 | 0.26 | 2.64 | 156.68 | 114.48 |
| crypto | 4h | C combo (med across N) | 0.71 | 0.17 | -0.15 | 0.25 | 3.38 | 75.09 | 51.97 |
| futures | 1d | A Donchian (med across N) | 0.30 | 0.28 | -0.16 | 0.49 | 1.47 | 10.57 | 14.36 |
| futures | 1d | B 50-SMA regime | 0.68 | 0.62 | -0.09 | 0.45 | 1.97 | 22.29 | 41.02 |
| futures | 1d | C combo (med across N) | 0.44 | 0.41 | -0.11 | 0.45 | 1.82 | 15.14 | 19.08 |
| futures | 4h | A Donchian (med across N) | 0.40 | 0.33 | -0.12 | 0.45 | 1.52 | 34.58 | 77.12 |
| futures | 4h | B 50-SMA regime | 0.53 | 0.34 | -0.18 | 0.35 | 2.09 | 107.09 | 238.59 |
| futures | 4h | C combo (med across N) | 0.39 | 0.27 | -0.13 | 0.38 | 2.05 | 55.42 | 117.61 |

- **crypto 1d**: C beats both pieces at **0 of 5** lookbacks (net Sharpe, channel exit).
- **crypto 4h**: C beats both pieces at **1 of 5** lookbacks (net Sharpe, channel exit).
- **futures 1d**: C beats both pieces at **0 of 5** lookbacks (net Sharpe, channel exit).
- **futures 4h**: C beats both pieces at **1 of 5** lookbacks (net Sharpe, channel exit).

## 4. Per-instrument (vol-scaled, channel exit, median across N; ranked by C net Sharpe)

Flag: CONSISTENT requires net Sharpe > 0 in both IS and OOS *and* a net-positive majority of the N-sweep (evaluated per config; flag shown here is for the instrument's median-N combo config).

### 1d

| Instrument | Group | B&H net SR | B net SR | A net SR (med N) | C net SR (med N) | Flag |
|---|---|---|---|---|---|---|
| BTC-USD | crypto | 0.96 | 1.41 | 0.80 | 1.05 | CONSISTENT |
| SOL-USD | crypto | 1.19 | 0.94 | 0.53 | 0.86 | CONSISTENT |
| ETH-USD | crypto | 0.66 | 1.01 | 0.64 | 0.86 | CONSISTENT |
| BNB-USD | crypto | 1.15 | 1.19 | 0.64 | 0.82 | CONSISTENT |
| AVAX-USD | crypto | 0.60 | 0.87 | 0.52 | 0.81 | CONSISTENT |
| ADA-USD | crypto | 0.70 | 0.71 | 0.54 | 0.61 | CONSISTENT |
| NQ=F | futures | 0.91 | 0.67 | 0.49 | 0.61 | FRAGILE |
| GC=F | futures | 0.94 | 0.43 | 0.42 | 0.56 | CONSISTENT |
| DOGE-USD | crypto | 0.81 | 0.84 | 0.33 | 0.46 | CONSISTENT |
| CL=F | futures | -0.28 | 0.50 | 0.45 | 0.44 | FRAGILE |
| ES=F | futures | 0.77 | 0.49 | 0.28 | 0.37 | CONSISTENT |
| DOT-USD | crypto | 0.30 | 0.37 | 0.35 | 0.37 | CONSISTENT |
| HG=F | futures | 0.59 | 0.22 | 0.08 | 0.12 | FRAGILE |
| ZN=F | futures | -0.33 | 0.24 | 0.02 | 0.09 | FRAGILE |
| LINK-USD | crypto | 0.93 | 0.32 | -0.34 | -0.05 | FRAGILE |
| ZB=F | futures | -0.36 | 0.20 | -0.13 | -0.11 | FRAGILE |
| XRP-USD | crypto | 0.69 | -0.17 | 0.06 | -0.12 | FRAGILE |
| YM=F | futures | 0.61 | 0.21 | -0.20 | -0.14 | FRAGILE |
| SI=F | futures | 0.72 | 0.13 | -0.25 | -0.15 | FRAGILE |
| NG=F | futures | 0.44 | -0.46 | -0.28 | -0.45 | FRAGILE |

### 4h

| Instrument | Group | B&H net SR | B net SR | A net SR (med N) | C net SR (med N) | Flag |
|---|---|---|---|---|---|---|
| GC=F | futures | 1.47 | 1.24 | 0.83 | 1.04 | CONSISTENT |
| ETH-USD | crypto | -0.01 | 0.07 | 0.59 | 0.46 | CONSISTENT |
| NQ=F | futures | 1.05 | 0.25 | 0.20 | 0.12 | FRAGILE |
| BTC-USD | crypto | 0.39 | -0.48 | 0.22 | -0.16 | FRAGILE |
| ES=F | futures | 1.10 | -0.77 | 0.12 | -0.23 | FRAGILE |

## 5. Out-of-sample (select best N & exit on IS only, run once on OOS)

Oldest 70% IS / newest 30% OOS on each group×timeframe's union calendar. Selection = highest IS EW-portfolio net Sharpe over the 10 (N, exit) pairs, per strategy family and sizing. Degradation = OOS − IS.

| Group | TF | Family | Sizing | N* | Exit* | IS net SR | OOS net SR | Degradation | B OOS | B&H OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| crypto | 1d | A Donchian breakout | fixed | 20 | atr | 1.51 | 0.34 | -1.18 | 0.45 | 0.61 |
| crypto | 1d | A Donchian breakout | volscaled | 20 | atr | 1.88 | 0.55 | -1.33 | 0.64 | 0.61 |
| crypto | 1d | C combo (A gated by B) | fixed | 55 | atr | 1.37 | 0.39 | -0.98 | 0.45 | 0.61 |
| crypto | 1d | C combo (A gated by B) | volscaled | 20 | atr | 1.78 | 0.60 | -1.18 | 0.64 | 0.61 |
| crypto | 4h | A Donchian breakout | fixed | 40 | atr | 0.99 | -0.04 | -1.04 | -0.41 | -1.12 |
| crypto | 4h | A Donchian breakout | volscaled | 40 | atr | 1.10 | 0.42 | -0.68 | -0.39 | -1.12 |
| crypto | 4h | C combo (A gated by B) | fixed | 40 | atr | 0.93 | -0.11 | -1.05 | -0.41 | -1.12 |
| crypto | 4h | C combo (A gated by B) | volscaled | 40 | atr | 1.12 | 0.33 | -0.79 | -0.39 | -1.12 |
| futures | 1d | A Donchian breakout | fixed | 80 | atr | 0.53 | -0.43 | -0.97 | 0.05 | 1.37 |
| futures | 1d | A Donchian breakout | volscaled | 80 | atr | 0.64 | -0.47 | -1.11 | 0.57 | 1.37 |
| futures | 1d | C combo (A gated by B) | fixed | 20 | atr | 0.54 | -0.18 | -0.72 | 0.05 | 1.37 |
| futures | 1d | C combo (A gated by B) | volscaled | 80 | atr | 0.65 | -0.36 | -1.02 | 0.57 | 1.37 |
| futures | 4h | A Donchian breakout | fixed | 80 | atr | 1.18 | -0.77 | -1.95 | -0.20 | 0.84 |
| futures | 4h | A Donchian breakout | volscaled | 80 | atr | 1.19 | -0.51 | -1.69 | -0.49 | 0.84 |
| futures | 4h | C combo (A gated by B) | fixed | 80 | atr | 1.20 | -0.89 | -2.10 | -0.20 | 0.84 |
| futures | 4h | C combo (A gated by B) | volscaled | 80 | atr | 1.20 | -0.73 | -1.92 | -0.49 | 0.84 |

## 6. Multiple-testing accounting

Total strategy configs evaluated (FULL sample, instrument- and portfolio-level, incl. the D diagnostic): **N = 1508**. Net annualized Sharpe distribution: mean 0.18, median 0.19, std 0.53, 5th pct -0.73, 95th pct 1.02.

| Top config | Net ann. SR | SR* (exp. max) | P(true SR>0) | Deflated SR P(SR>SR*) |
|---|---|---|---|---|
| crypto 1d A Donchian breakout/atr N=20 volscaled (EW_PORTFOLIO) | 1.53 | 1.80 | 1.00 | 0.17 |
| crypto 1d C combo (A gated by B)/atr N=20 volscaled (EW_PORTFOLIO) | 1.47 | 1.80 | 1.00 | 0.12 |
| crypto 1d C combo (A gated by B)/atr N=10 volscaled (EW_PORTFOLIO) | 1.47 | 1.80 | 1.00 | 0.12 |
| crypto 1d B 50-SMA regime/ N=0 volscaled (EW_PORTFOLIO) | 1.42 | 1.80 | 1.00 | 0.09 |
| crypto 1d B 50-SMA regime/ N=0 volscaled (BTC-USD) | 1.41 | 1.80 | 1.00 | 0.08 |
| crypto 1d C combo (A gated by B)/channel N=10 volscaled (EW_PORTFOLIO) | 1.39 | 1.80 | 1.00 | 0.07 |
| futures 4h C combo (A gated by B)/channel N=80 volscaled (GC=F) | 1.38 | 1.80 | 0.98 | 0.26 |
| crypto 1d C combo (A gated by B)/atr N=55 volscaled (EW_PORTFOLIO) | 1.37 | 1.80 | 1.00 | 0.06 |

Note the trials are highly correlated (same five strategies across overlapping instruments) and include the deliberately-bad D diagnostic, both of which make SR\* and this deflation conservative — the effective number of independent trials is well below 1508. Even so, no top config clears 0.5.

## 7. Plain-English answers to the six questions

**Q1 — Does Donchian breakout capture trend?**
- crypto 1d: median gross Sharpe 0.82 across the N-sweep (net 0.77); IS-selected config OOS net Sharpe 0.55.
- crypto 4h: median gross Sharpe 0.70 across the N-sweep (net 0.40); IS-selected config OOS net Sharpe 0.42.
- futures 1d: median gross Sharpe 0.30 across the N-sweep (net 0.28); IS-selected config OOS net Sharpe -0.47.
- futures 4h: median gross Sharpe 0.40 across the N-sweep (net 0.33); IS-selected config OOS net Sharpe -0.51.

**Q2 — Which lookback N is robust?** Portfolio net Sharpe (channel exit) by N, positive-count across the four group×timeframe blocks:
- N=10: positive in 4/4 blocks (1.26, 0.66, 0.03, 0.42).
- N=20: positive in 4/4 blocks (1.30, 0.30, 0.12, 0.65).
- N=40: positive in 4/4 blocks (0.77, 0.53, 0.47, 0.33).
- N=55: positive in 4/4 blocks (0.74, 0.19, 0.29, 0.21).
- N=80: positive in 4/4 blocks (0.70, 0.40, 0.28, 0.31).

**Q3 — Does the combination beat each piece alone?**
- crypto 1d: A med 0.77, B 1.42, C med 1.15 → combo beats both at 0/5 lookbacks; on medians it does NOT beat the better single piece.
- crypto 4h: A med 0.40, B -0.23, C med 0.17 → combo beats both at 1/5 lookbacks; on medians it does NOT beat the better single piece.
- futures 1d: A med 0.28, B 0.62, C med 0.41 → combo beats both at 0/5 lookbacks; on medians it does NOT beat the better single piece.
- futures 4h: A med 0.33, B 0.34, C med 0.27 → combo beats both at 1/5 lookbacks; on medians it does NOT beat the better single piece.

**Q4 — Trend or mean-reversion at the bands?** Median GROSS Sharpe of the fade strategy (D) across N — negative means breakouts continue (trend), positive means they revert:
- crypto 1d: fade gross -1.06 vs breakout gross 0.82 → TRENDS at the band.
- crypto 4h: fade gross -0.74 vs breakout gross 0.70 → TRENDS at the band.
- futures 1d: fade gross -0.43 vs breakout gross 0.30 → TRENDS at the band.
- futures 4h: fade gross -0.46 vs breakout gross 0.40 → TRENDS at the band.

**Q5 — Structural channel exit vs 3×ATR chandelier?** Median net Sharpe across N (A family):
- crypto 1d: channel 0.77 vs ATR 1.33 → ATR better.
- crypto 4h: channel 0.40 vs ATR 0.76 → ATR better.
- futures 1d: channel 0.28 vs ATR 0.30 → ATR better.
- futures 4h: channel 0.33 vs ATR 0.44 → ATR better.
- Channel exit wins 0/4 blocks.

**Q6 — Crypto vs futures, cleaner structural trend?**
- crypto: median gross Sharpe 0.78, median net 0.68 across all N and timeframes.
- futures: median gross Sharpe 0.34, median net 0.30 across all N and timeframes.
- Reminder: futures numbers are polluted by front-month roll gaps, which fire spurious breakouts in both directions; crypto spot is the clean read.

**Bottom line.** The structural trend definition is real but the combination is not: Donchian breakouts are gross-positive at every lookback in every block while the fade of the same bands is negative everywhere, so N-bar extremes do mark continuation, not reversal — the channel 'sees' trend. But the 50-SMA regime gate does not earn its keep on top of the breakout (it never beats the better single piece on medians), the 3×ATR chandelier beats the structural N/2-channel exit in every block, and out-of-sample everything degrades — crypto gracefully (positive but roughly a third of IS, and no better than the plain 50-SMA regime OOS), futures to outright negative (collapse; roll gaps make even the in-sample futures read suspect). Nothing clears the deflated-Sharpe bar of best-of-1508 luck, and buy-and-hold (net Sharpe crypto/1d 1.21, crypto/4h 0.16, futures/1d 0.51, futures/4h 1.55) remains hard to beat. As exploratory evidence: the reactive structural trigger captures trend on crypto daily bars; the extra regime-filter complexity does not add value there.

---
*Reproduce: `python backtest.py` (or `--cached` for the committed data snapshot). All configs: `output/results_all_configs.csv` (`period` ∈ FULL/IS/OOS; strategies: donch_break=A, sma50_regime=B, combo=C, donch_fade=D, buyhold).*