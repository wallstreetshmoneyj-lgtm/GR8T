# Intraday regime assessment — BULL/BEAR/CHOP vs a random-walk null

Tests whether market regime can be mechanically assessed on **1h and 4h
bars** as one of three concurrent states — BULL, BEAR, CHOP — for 10
crypto pairs and 10 futures. Descriptive classification only: no trades,
no prediction claims. A classifier "works" only if its three buckets show
forward behavior (drift, persistence, volatility, efficiency) that
**exceeds what the identical classifier produces on block-shuffled
returns** (stationary bootstrap, mean block 10, B=1000, seeded,
OHLC-geometry preserving).

Classifiers: **ADX(14)** (<20 = CHOP, else ±DI direction), **Kaufman ER**
(20-bar, <0.30 = CHOP, else sign of net change), **3-state Gaussian HMM**
(fit once on in-sample 70%, frozen model + scaler decodes real and null
series alike; Viterbi smoothing caveat flagged in the report), and — only
because all three failed the pre-registered criterion — the
**pre-registered market-structure fallback** (k=3 fractal swings, HH/HL =
BULL, LH/LL = BEAR, mixed/stale/close-based-break = CHOP).

Pre-registered pass bar (fixed before results): ≥25% of a classifier's
40 instrument×timeframe configs must beat the null at p<0.05 on the
BULL−BEAR forward-drift spread (S1), FULL window.

**Headline (see `output/SUMMARY.md`):** all four classifiers fail —
configs beating the null sit at the ~5% false-positive rate, drift
separations are fractions of a basis point, and the fallback does no
better. These markets do not yield a mechanically-validated three-state
regime label at 1h/4h; the exploitable object remains the weak
probabilistic crypto persistence at daily/weekly horizons found in the
prior studies.

## Files

- `regime_scoring.py` — full pipeline (classifiers → scoring → null → report)
- `output/SUMMARY.md` — paste-ready report answering the six questions
- `output/regime_metrics.csv` — every classifier×instrument×timeframe×window
  row with per-regime metrics, null means/percentiles, z-scores, p-values

Data: 1h snapshots (own `data/` plus reuse of `../donchian_regime/data/`);
4h resampled from 1h anchored to UTC midnight. Futures are front-month
continuous with roll gaps — flagged throughout.

## Run

```bash
.venv/bin/python regime_scoring.py          # B=1000 (~1h, seeded)
.venv/bin/python regime_scoring.py --fast   # B=150 smoke test (~10 min)
```
