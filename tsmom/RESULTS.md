# TSMOM robustness search — results

Latest bar: **2026-07-07** · instruments loaded: **39** · costs per unit turnover: fx 1bp / fut 2bp / crypto 20bp · sizing 'vol' = 15% target, 60d realized, 3x cap.

Dropped instruments: MATIC (stale (last bar 2025-03-24)).

## (a) Stage 1 — per-instrument net Sharpe (multi-horizon composite, vol-scaled)

| instrument | group | net Sharpe 5y | 3y | 1y | flag |
|---|---|---|---|---|---|
| SOL | crypto | +0.81 | +0.66 | -0.15 | FRAGILE |
| BTC | crypto | +0.80 | +0.95 | +0.52 | CONSISTENT |
| GC | futures | +0.70 | +1.37 | +1.80 | CONSISTENT |
| AVAX | crypto | +0.69 | +0.55 | +0.76 | CONSISTENT |
| USDJPY | forex | +0.67 | +0.02 | +0.35 | CONSISTENT |
| ES | futures | +0.49 | +0.85 | +0.91 | CONSISTENT |
| ADA | crypto | +0.49 | +0.68 | +0.97 | CONSISTENT |
| ETH | crypto | +0.46 | +0.48 | +1.28 | CONSISTENT |
| 6J | futures | +0.44 | -0.27 | -0.57 | FRAGILE |
| NQ | futures | +0.43 | +0.43 | +0.76 | CONSISTENT |
| DOGE | crypto | +0.37 | +1.03 | +1.04 | CONSISTENT |
| AUDJPY | forex | +0.24 | +0.26 | +1.11 | CONSISTENT |
| BNB | crypto | +0.22 | +0.26 | +1.05 | CONSISTENT |
| SI | futures | +0.19 | +0.66 | +2.07 | CONSISTENT |
| YM | futures | +0.14 | +0.60 | +1.00 | CONSISTENT |
| EURUSD | forex | +0.13 | -0.19 | -0.44 | FRAGILE |
| ZC | futures | +0.09 | -0.01 | -0.86 | FRAGILE |
| DOT | crypto | +0.06 | +0.20 | +0.70 | CONSISTENT |
| ZS | futures | +0.04 | +0.06 | +0.33 | CONSISTENT |
| 6E | futures | -0.01 | -0.15 | -0.05 | FRAGILE |
| GBPJPY | forex | -0.12 | -0.32 | +0.29 | FRAGILE |
| EURJPY | forex | -0.12 | -0.21 | +0.67 | FRAGILE |
| NG | futures | -0.14 | -0.78 | -1.51 | FRAGILE |
| CL | futures | -0.16 | -0.20 | +0.85 | FRAGILE |
| XRP | crypto | -0.18 | +0.29 | +0.82 | FRAGILE |
| GBPUSD | forex | -0.22 | -0.84 | -1.53 | FRAGILE |
| HG | futures | -0.22 | +0.08 | +0.23 | FRAGILE |
| LINK | crypto | -0.24 | +0.10 | +0.58 | FRAGILE |
| AUDUSD | forex | -0.32 | -0.53 | +0.18 | FRAGILE |
| EURGBP | forex | -0.35 | -0.45 | -0.25 | FRAGILE |
| RTY | futures | -0.36 | +0.05 | +0.72 | FRAGILE |
| ZN | futures | -0.38 | -1.11 | -1.56 | FRAGILE |
| LTC | crypto | -0.40 | -0.33 | +0.58 | FRAGILE |
| ZB | futures | -0.41 | -0.80 | -1.53 | FRAGILE |
| ZW | futures | -0.44 | -1.19 | -0.40 | FRAGILE |
| EURCHF | forex | -0.46 | -0.61 | -0.82 | FRAGILE |
| USDCHF | forex | -0.56 | -0.17 | -1.01 | FRAGILE |
| NZDUSD | forex | -0.57 | -0.72 | -0.59 | FRAGILE |
| USDCAD | forex | -0.62 | -0.44 | +0.35 | FRAGILE |

## (b) Stage 1 — group portfolios (vol-scaled, net Sharpe)

| group | signal | 5y | 3y | 1y |
|---|---|---|---|---|
| crypto | 10 | +0.11 | +0.12 | -0.11 |
| crypto | 20 | +0.11 | +0.34 | +0.15 |
| crypto | 40 | +0.27 | +0.59 | +0.70 |
| crypto | 60 | +0.33 | +0.78 | +0.77 |
| crypto | 120 | +0.57 | +0.83 | +1.33 |
| crypto | 180 | -0.27 | +0.10 | +0.34 |
| crypto | 250 | +0.17 | -0.18 | +0.79 |
| crypto | composite | +0.40 | +0.65 | +0.93 |
| forex | 10 | -0.50 | -1.04 | -1.93 |
| forex | 20 | -0.56 | -0.33 | -0.56 |
| forex | 40 | -0.44 | -0.33 | -1.17 |
| forex | 60 | -0.39 | -0.69 | -0.90 |
| forex | 120 | -0.35 | -0.86 | +0.31 |
| forex | 180 | +0.13 | -0.23 | +0.13 |
| forex | 250 | +0.21 | -0.10 | +0.79 |
| forex | composite | -0.36 | -0.66 | -0.13 |
| futures | 10 | -0.29 | -0.52 | -1.47 |
| futures | 20 | -0.25 | -0.24 | -0.36 |
| futures | 40 | -0.02 | +0.17 | +0.88 |
| futures | 60 | -0.13 | -0.12 | +0.79 |
| futures | 120 | +0.09 | +0.15 | +1.53 |
| futures | 180 | +0.25 | +0.55 | +0.93 |
| futures | 250 | +0.58 | +0.60 | +0.64 |
| futures | composite | +0.10 | +0.12 | +0.79 |

Best group config in-sample-recent (5y): **futures @ signal 250** with net Sharpe +0.58.

## (c) Stage 2 — out-of-sample validation (selection on oldest 70% only)

| config | IS net Sharpe | OOS net Sharpe | degradation | OOS ann ret | OOS maxDD | OOS t-stat |
|---|---|---|---|---|---|---|
| crypto @ L=120 (group, vol) | +1.09 | +0.57 | -0.52 | +6.2% | 12.3% | +0.82 |
| forex @ L=250 (group, vol) | +0.42 | -0.30 | -0.71 | -2.3% | 12.0% | -0.44 |
| futures @ L=250 (group, vol) | +1.01 | +0.31 | -0.70 | +1.6% | 5.3% | +0.45 |
| BEST OVERALL: crypto @ 120 (group, vol) | +1.09 | +0.57 | -0.52 | +6.2% | 12.3% | +0.82 |
| SOL composite (instrument, vol) | +1.45 | -0.09 | -1.54 | -1.6% | 18.6% | -0.13 |
| BTC composite (instrument, vol) | +1.28 | +0.51 | -0.78 | +5.3% | 10.8% | +0.73 |
| ETH composite (instrument, vol) | +1.15 | +0.32 | -0.83 | +3.0% | 10.6% | +0.47 |

## (d) Multiple-testing accounting

* Total configs tested (stage-1 5y rows, instrument + group, both sizings): **N = 672**
* Stage-1 net-Sharpe distribution: mean -0.02, median -0.04, std 0.39, 5th pct -0.63, 95th pct +0.67
* Under a zero-edge null, a 5y measured Sharpe has std ≈ 1/√5 ≈ 0.45, so P(net Sharpe > 0.5 by chance) ≈ 13% per independent trial → ≈ **89 of 672** configs would clear 0.5 by luck alone (fewer effective independent trials due to correlation, but the order of magnitude stands).
* Observed configs with 5y net Sharpe > 0.5: **65**

### Regular vs Deflated Sharpe (5y net returns; N and trial variance as above)

| config | ann Sharpe (5y) | deflated Sharpe (haircut) | P(true SR > 0) after selection |
|---|---|---|---|
| crypto @ L=120 (group, vol) | +0.57 | -0.66 | 7% |
| forex @ L=250 (group, vol) | +0.21 | -1.02 | 1% |
| futures @ L=250 (group, vol) | +0.58 | -0.65 | 8% |
| BEST OVERALL: crypto @ 120 (group, vol) | +0.57 | -0.66 | 7% |
| SOL composite (instrument, vol) | +0.81 | -0.42 | 17% |
| BTC composite (instrument, vol) | +0.80 | -0.44 | 16% |
| ETH composite (instrument, vol) | +0.46 | -0.77 | 4% |

## Reference — buy & hold (5y, net Sharpe)

* EW long crypto: Sharpe +0.33, ann ret -1.3%, maxDD 81%  (arithmetic-Sharpe positive, geometric return negative = vol drag)
* EW long forex: Sharpe +0.45, ann ret +1.7%, maxDD 6%
* EW long futures: Sharpe +0.70, ann ret +7.6%, maxDD 17%

## (e) Verdict

**Nothing survives all four filters (net-positive + CONSISTENT + OOS + deflated Sharpe).**

1. **The config universe as a whole is indistinguishable from noise minus costs.** The
   stage-1 net-Sharpe distribution is centered at ~0 (mean −0.02, median −0.04), and the
   number of configs clearing net Sharpe 0.5 (65) is *below* the ~89 that pure chance
   would produce across N=672 correlated trials. No deflated Sharpe among the top configs
   exceeds P(true SR > 0) = 17%.
2. **Two partial survivors — hypotheses, not proven edges:** group-level **crypto @ 120d**
   (IS +1.09 → OOS +0.57; positive in all three stage-1 windows; DSR only 7%) and
   **futures @ 250d** (strikingly stable +0.58/+0.60/+0.64 across 5y/3y/1y; OOS +0.31;
   DSR 8%). Both *degrade gracefully* out-of-sample rather than collapse, and both sit at
   the classic Moskowitz–Ooi–Pedersen horizons (long lookbacks), which is the direction
   the literature predicts. They are underpowered on ~7 years of data, not disproven.
3. **Forex TSMOM is dead** net of costs at every horizon (best 5y +0.21; OOS −0.30).
4. **Short lookbacks (10–40d) are negative everywhere** — consistent with the prior that
   the effect lives at 1–12 months, not days.
5. **Instrument-level standouts are mostly selection luck.** SOL (best IS instrument,
   +1.45) collapsed to −0.09 OOS = overfit. BTC degraded gracefully (+1.28 → +0.51).
   GC's +0.70/+1.37/+1.80 rides one historic gold trend — a hypothesis at best.
6. **Nothing beats buy & hold:** EW-long futures earned net Sharpe +0.70 over 5y — higher
   than every TSMOM group config net of costs.

**Caveats:** Yahoo `=F` are front-month continuous series with roll gaps (distorts slow
signals — a proper test needs back-adjusted futures, e.g. Nasdaq Data Link / Databento);
~7y of daily data is short for 12-month momentum (MOP used 25+ years); one contiguous OOS
block, not walk-forward; costs are stylized constants.

**If pursued further:** only the group-level, long-horizon (120–250d), vol-scaled configs in
crypto and futures merit a retest — on longer, back-adjusted data, benchmarked against
simple long exposure, with walk-forward validation.
