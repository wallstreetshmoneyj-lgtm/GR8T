# Intraday regime assessment — BULL/BEAR/CHOP vs a random-walk null (1h & 4h, crypto vs futures)

*Run date: 2026-07-10. Concurrent regime CLASSIFICATION only — no trades, no prediction claims. Null = stationary block bootstrap (B=1000, mean block 10 bars, seeded) of each instrument's own bars, preserving return distribution and per-bar OHLC geometry. p-values are one-sided empirical P(null ≥ real). 4h bars are resampled from 1h anchored to UTC midnight (native 4h unused, for cross-group consistency). **Futures are front-month continuous with roll gaps that contaminate both the real and null regime states — back-adjusted contracts are needed for firm futures conclusions.** HMM caveat: states are fit once on the in-sample 70% and decoded with Viterbi (a smoothing decode — the label at bar t uses the whole sequence); the null is decoded with the same frozen model, keeping the comparison like-for-like. Pre-registered pass criterion: ≥25% of a classifier's configs with BULL−BEAR forward-drift spread (S1) beating the null at p<0.05 on the FULL window.*

## 1. Sample sizes

| Group | TF | Instrument | Start | End | Bars | Bars/yr |
|---|---|---|---|---|---|---|
| crypto | 1h | ADA-USD | 2024-07-11 | 2026-07-10 | 17464 | 8748 |
| crypto | 1h | AVAX-USD | 2024-07-11 | 2026-07-10 | 17464 | 8748 |
| crypto | 1h | BNB-USD | 2024-07-11 | 2026-07-10 | 17467 | 8749 |
| crypto | 1h | BTC-USD | 2024-07-08 | 2026-07-07 | 17483 | 8749 |
| crypto | 1h | DOGE-USD | 2024-07-11 | 2026-07-10 | 17465 | 8748 |
| crypto | 1h | DOT-USD | 2024-07-11 | 2026-07-10 | 17466 | 8749 |
| crypto | 1h | ETH-USD | 2024-07-08 | 2026-07-07 | 17480 | 8748 |
| crypto | 1h | LINK-USD | 2024-07-11 | 2026-07-10 | 17464 | 8748 |
| crypto | 1h | SOL-USD | 2024-07-11 | 2026-07-10 | 17466 | 8749 |
| crypto | 1h | XRP-USD | 2024-07-11 | 2026-07-10 | 17467 | 8749 |
| futures | 1h | CL=F | 2024-02-15 | 2026-07-10 | 13497 | 5628 |
| futures | 1h | ES=F | 2024-02-12 | 2026-07-07 | 13694 | 5706 |
| futures | 1h | GC=F | 2024-02-12 | 2026-07-07 | 13734 | 5722 |
| futures | 1h | HG=F | 2024-02-15 | 2026-07-10 | 13711 | 5717 |
| futures | 1h | NG=F | 2024-02-15 | 2026-07-10 | 13483 | 5622 |
| futures | 1h | NQ=F | 2024-02-12 | 2026-07-07 | 13691 | 5704 |
| futures | 1h | SI=F | 2024-02-15 | 2026-07-10 | 13714 | 5718 |
| futures | 1h | YM=F | 2024-02-15 | 2026-07-10 | 13670 | 5700 |
| futures | 1h | ZB=F | 2024-02-15 | 2026-07-10 | 13637 | 5686 |
| futures | 1h | ZN=F | 2024-02-15 | 2026-07-10 | 13639 | 5687 |
| crypto | 4h | ADA-USD | 2024-07-11 | 2026-07-09 | 4368 | 2188 |
| crypto | 4h | AVAX-USD | 2024-07-11 | 2026-07-09 | 4368 | 2188 |
| crypto | 4h | BNB-USD | 2024-07-11 | 2026-07-09 | 4368 | 2188 |
| crypto | 4h | BTC-USD | 2024-07-08 | 2026-07-07 | 4372 | 2188 |
| crypto | 4h | DOGE-USD | 2024-07-11 | 2026-07-09 | 4368 | 2188 |
| crypto | 4h | DOT-USD | 2024-07-11 | 2026-07-09 | 4368 | 2188 |
| crypto | 4h | ETH-USD | 2024-07-08 | 2026-07-07 | 4372 | 2188 |
| crypto | 4h | LINK-USD | 2024-07-11 | 2026-07-09 | 4368 | 2188 |
| crypto | 4h | SOL-USD | 2024-07-11 | 2026-07-09 | 4368 | 2188 |
| crypto | 4h | XRP-USD | 2024-07-11 | 2026-07-09 | 4368 | 2188 |
| futures | 4h | CL=F | 2024-02-15 | 2026-07-09 | 3678 | 1534 |
| futures | 4h | ES=F | 2024-02-12 | 2026-07-07 | 3712 | 1547 |
| futures | 4h | GC=F | 2024-02-12 | 2026-07-07 | 3720 | 1550 |
| futures | 4h | HG=F | 2024-02-15 | 2026-07-09 | 3716 | 1550 |
| futures | 4h | NG=F | 2024-02-15 | 2026-07-09 | 3672 | 1531 |
| futures | 4h | NQ=F | 2024-02-12 | 2026-07-07 | 3709 | 1545 |
| futures | 4h | SI=F | 2024-02-15 | 2026-07-09 | 3716 | 1550 |
| futures | 4h | YM=F | 2024-02-15 | 2026-07-09 | 3706 | 1545 |
| futures | 4h | ZB=F | 2024-02-15 | 2026-07-09 | 3691 | 1539 |
| futures | 4h | ZN=F | 2024-02-15 | 2026-07-09 | 3691 | 1539 |

No series skipped.

## 2. Regime separation vs null (classifier × group × timeframe)

S1 = mean forward drift(BULL) − drift(BEAR), in bps/bar. `beat` = share of instruments with S1 p<0.05 vs the null; same for the Kruskal-Wallis H across the three buckets. Medians across instruments; FULL window, with OOS S1 alongside.

| Classifier | Group | TF | S1 (bps) | S1 null mean | S1 p (med) | S1 beat null | KW beat null | OOS S1 (bps) | OOS beat | CHOP share |
|---|---|---|---|---|---|---|---|---|---|---|
| ADX | crypto | 1h | 0.70 | 0.37 | 0.41 | 1/10 | 1/10 | -1.05 | 0/10 | 0.32 |
| ADX | crypto | 4h | -0.80 | 0.09 | 0.56 | 0/10 | 0/10 | -3.41 | 0/10 | 0.32 |
| ADX | futures | 1h | -0.11 | -0.03 | 0.50 | 0/10 | 0/10 | -0.17 | 0/10 | 0.28 |
| ADX | futures | 4h | -0.11 | -0.16 | 0.50 | 0/10 | 1/10 | -2.93 | 0/10 | 0.31 |
| ER | crypto | 1h | 2.24 | 0.69 | 0.23 | 1/10 | 1/10 | 0.35 | 0/10 | 0.68 |
| ER | crypto | 4h | 5.02 | 2.34 | 0.35 | 0/10 | 0/10 | -15.67 | 0/10 | 0.67 |
| ER | futures | 1h | 0.15 | -0.24 | 0.38 | 1/10 | 0/10 | -0.28 | 1/10 | 0.64 |
| ER | futures | 4h | -1.14 | -0.61 | 0.60 | 0/10 | 0/10 | -5.60 | 1/10 | 0.63 |
| HMM | crypto | 1h | 0.51 | -0.13 | 0.51 | 0/10 | 0/10 | -1.82 | 0/10 | 0.35 |
| HMM | crypto | 4h | 2.73 | 0.53 | 0.40 | 1/10 | 0/10 | -1.08 | 0/10 | 0.38 |
| HMM | futures | 1h | 0.09 | 0.23 | 0.61 | 0/10 | 0/10 | -0.83 | 1/10 | 0.40 |
| HMM | futures | 4h | 1.28 | 0.47 | 0.41 | 0/10 | 0/10 | -0.42 | 0/10 | 0.43 |
| SWING | crypto | 1h | 0.29 | 0.21 | 0.48 | 0/10 | 2/10 | -0.42 | 0/10 | 0.51 |
| SWING | crypto | 4h | 1.14 | 1.23 | 0.47 | 0/10 | 0/10 | -5.54 | 0/10 | 0.50 |
| SWING | futures | 1h | -0.39 | -0.03 | 0.71 | 0/10 | 0/10 | -0.17 | 1/10 | 0.59 |
| SWING | futures | 4h | -0.84 | -0.38 | 0.62 | 0/10 | 0/10 | -1.54 | 0/10 | 0.49 |

## 3. Per-regime forward behavior (medians across instruments, FULL window)

### ADX

| Group | TF | Drift BULL (bps) | Drift CHOP | Drift BEAR | Vol BULL | Vol CHOP | Vol BEAR | AC1 trend | AC1 chop | Eff trend | Eff chop |
|---|---|---|---|---|---|---|---|---|---|---|---|
| crypto | 1h | 0.68 | -0.60 | -0.15 | 0.86 | 0.74 | 0.90 | -0.00 | 0.02 | 0.22 | 0.37 |
| crypto | 4h | -0.17 | -0.63 | 0.69 | 0.88 | 0.71 | 0.86 | 0.00 | 0.02 | 0.23 | 0.40 |
| futures | 1h | 0.33 | 0.54 | 0.12 | 0.19 | 0.20 | 0.24 | -0.05 | 0.00 | 0.24 | 0.39 |
| futures | 4h | 0.05 | 1.08 | 0.79 | 0.19 | 0.18 | 0.27 | 0.00 | 0.00 | 0.28 | 0.38 |

### ER

| Group | TF | Drift BULL (bps) | Drift CHOP | Drift BEAR | Vol BULL | Vol CHOP | Vol BEAR | AC1 trend | AC1 chop | Eff trend | Eff chop |
|---|---|---|---|---|---|---|---|---|---|---|---|
| crypto | 1h | 1.23 | 0.05 | -0.16 | 0.87 | 0.78 | 1.00 | -0.00 | 0.00 | 0.33 | 0.31 |
| crypto | 4h | 3.65 | -1.58 | -0.18 | 0.83 | 0.75 | 1.01 | -0.02 | 0.01 | 0.34 | 0.33 |
| futures | 1h | 0.24 | 0.44 | 0.10 | 0.18 | 0.21 | 0.29 | -0.01 | -0.02 | 0.36 | 0.33 |
| futures | 4h | 0.96 | 1.29 | 0.87 | 0.18 | 0.22 | 0.27 | -0.02 | 0.00 | 0.39 | 0.35 |

### HMM

| Group | TF | Drift BULL (bps) | Drift CHOP | Drift BEAR | Vol BULL | Vol CHOP | Vol BEAR | AC1 trend | AC1 chop | Eff trend | Eff chop |
|---|---|---|---|---|---|---|---|---|---|---|---|
| crypto | 1h | 0.07 | -0.25 | -0.17 | 0.61 | 0.64 | 0.84 | -0.01 | 0.00 | 0.21 | 0.27 |
| crypto | 4h | 1.08 | -0.65 | -0.75 | 0.83 | 0.65 | 0.86 | -0.00 | 0.03 | 0.20 | 0.21 |
| futures | 1h | 0.33 | 0.19 | 0.42 | 0.14 | 0.18 | 0.36 | -0.01 | -0.01 | 0.24 | 0.25 |
| futures | 4h | 1.54 | 0.68 | 0.28 | 0.14 | 0.24 | 0.31 | 0.00 | 0.01 | 0.24 | 0.25 |

### SWING

| Group | TF | Drift BULL (bps) | Drift CHOP | Drift BEAR | Vol BULL | Vol CHOP | Vol BEAR | AC1 trend | AC1 chop | Eff trend | Eff chop |
|---|---|---|---|---|---|---|---|---|---|---|---|
| crypto | 1h | 0.45 | 0.06 | -0.11 | 0.84 | 0.82 | 0.89 | 0.01 | 0.01 | 0.24 | 0.30 |
| crypto | 4h | -0.90 | 1.49 | -1.86 | 0.82 | 0.83 | 0.85 | -0.02 | 0.01 | 0.25 | 0.31 |
| futures | 1h | 0.43 | 0.38 | 0.35 | 0.20 | 0.21 | 0.25 | -0.01 | -0.02 | 0.29 | 0.31 |
| futures | 4h | 0.60 | 1.33 | 1.68 | 0.20 | 0.21 | 0.26 | -0.01 | -0.01 | 0.27 | 0.36 |

## 4. Does the CHOP state work? (trend-minus-chop diffs vs null)

d_eff = per-segment efficiency of trend states minus CHOP; d_ac1 = lag-1 autocorr of trend states minus CHOP. Positive and beating the null would mean CHOP genuinely isolates the low-persistence, going-nowhere bars. ER's own d_eff is partially circular (it labels by trailing efficiency) — flagged, judge it on drift/persistence.

| Classifier | Group | TF | d_eff | d_eff beat null | d_ac1 | d_ac1 beat null | |CHOP drift| smallest |
|---|---|---|---|---|---|---|---|
| ADX | crypto | 1h | -0.16 | 0/10 | -0.02 | 0/10 | 3/10 |
| ADX | crypto | 4h | -0.18 | 0/10 | -0.02 | 0/10 | 1/10 |
| ADX | futures | 1h | -0.15 | 0/10 | -0.05 | 0/10 | 3/10 |
| ADX | futures | 4h | -0.11 | 0/10 | -0.00 | 0/10 | 2/10 |
| ER | crypto | 1h | 0.02 | 1/10 | 0.01 | 0/10 | 6/10 |
| ER | crypto | 4h | 0.00 | 0/10 | -0.01 | 0/10 | 4/10 |
| ER | futures | 1h | 0.02 | 0/10 | 0.01 | 1/10 | 5/10 |
| ER | futures | 4h | 0.03 | 1/10 | 0.00 | 0/10 | 5/10 |
| HMM | crypto | 1h | -0.03 | 0/10 | -0.02 | 0/10 | 5/10 |
| HMM | crypto | 4h | 0.01 | 0/10 | -0.03 | 0/10 | 7/10 |
| HMM | futures | 1h | -0.01 | 1/10 | -0.02 | 0/10 | 4/10 |
| HMM | futures | 4h | -0.00 | 0/10 | -0.01 | 0/10 | 6/10 |
| SWING | crypto | 1h | -0.05 | 0/10 | -0.01 | 0/10 | 4/10 |
| SWING | crypto | 4h | -0.06 | 0/10 | -0.01 | 0/10 | 5/10 |
| SWING | futures | 1h | -0.03 | 2/10 | 0.01 | 1/10 | 3/10 |
| SWING | futures | 4h | -0.08 | 0/10 | -0.01 | 0/10 | 3/10 |

## 5. Timeframe and asset-class comparison (share of configs beating null on S1, FULL)

| Axis | Value | Configs beating null | Share |
|---|---|---|---|
| timeframe | 1h | 3/80 | 0.04 |
| timeframe | 4h | 1/80 | 0.01 |
| group | crypto | 3/80 | 0.04 |
| group | futures | 1/80 | 0.01 |

## 6. Plain-English answers

**Q1 — Can regime be mechanically assessed on 4h/1h?**
- ADX 1h: 5% of 20 configs beat the null on BULL−BEAR separation (OOS: 0%) → NO by the pre-registered bar.
- ADX 4h: 0% of 20 configs beat the null on BULL−BEAR separation (OOS: 0%) → NO by the pre-registered bar.
- ER 1h: 10% of 20 configs beat the null on BULL−BEAR separation (OOS: 5%) → NO by the pre-registered bar.
- ER 4h: 0% of 20 configs beat the null on BULL−BEAR separation (OOS: 5%) → NO by the pre-registered bar.
- HMM 1h: 0% of 20 configs beat the null on BULL−BEAR separation (OOS: 5%) → NO by the pre-registered bar.
- HMM 4h: 5% of 20 configs beat the null on BULL−BEAR separation (OOS: 0%) → NO by the pre-registered bar.
- SWING 1h: 0% of 20 configs beat the null on BULL−BEAR separation (OOS: 5%) → NO by the pre-registered bar.
- SWING 4h: 0% of 20 configs beat the null on BULL−BEAR separation (OOS: 0%) → NO by the pre-registered bar.

**Q2 — Which classifier separates best?** Ranked by share of configs beating the null on S1 (FULL): ER (5%), ADX (2%), HMM (2%), SWING (0%). Pre-registered verdicts: ADX: FAIL, ER: FAIL, HMM: FAIL, SWING: FAIL.

**Q3 — Does the CHOP state actually work?** Share of configs where trend-minus-chop efficiency / persistence beats the null: ADX: eff 0%, ac1 0%; ER: eff 5%, ac1 2%; HMM: eff 2%, ac1 0%; SWING: eff 5%, ac1 2%.

**Q4 — 1h vs 4h:** configs beating the null on S1 — 1h: 4% of 80, 4h: 1% of 80.

**Q5 — crypto vs futures:** configs beating the null on S1 — crypto: 4% of 80, futures: 1% of 80.

**Q6 — Cosmetic labels:** ADX, ER, HMM, SWING did not beat the shuffled null at the pre-registered bar — their BULL/BEAR/CHOP labels partition bars in ways statistically indistinguishable from the same labels drawn on block-shuffled (structureless) data. Those regime labels are cosmetic at these timeframes.

**Fallback verdict:** the pre-registered market-structure classifier ALSO failed the identical test. The honest conclusion is that these markets do not yield a mechanically-validated three-state regime label at 1h/4h; the exploitable object remains the weak probabilistic crypto persistence at daily/weekly horizons found in the prior studies.

---
*Total configs evaluated: 4 classifiers × 20 instruments × 2 timeframes, windows FULL/IS/OOS; all metrics incl. null means/percentiles/p-values in `output/regime_metrics.csv`. Reproduce: `python regime_scoring.py` (seeded).*