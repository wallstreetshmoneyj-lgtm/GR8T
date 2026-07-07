# Donchian breakout + 50-SMA regime filter — marginal-contribution study

Tests whether a structural trend trigger (pure N-bar high/low Donchian
breakout, no smoothing) captures trend on crypto and futures, and whether
gating it with the 50-SMA regime filter adds marginal value over either
piece alone. Daily bars (crypto max history, futures ~7y front-month
continuous) plus a 4h cross-check (BTC, ETH, ES, NQ, GC; ~2y, Yahoo cap).

Strategies: **A** Donchian breakout (N ∈ {10,20,40,55,80}; exits: opposite
N/2 channel vs 3×ATR(20) chandelier), **B** 50-SMA regime alone, **C** the
combination (A gated by B, flat on disagreement), **D** band-fade
reversion diagnostic, plus buy & hold. Vol-scaled (15%/3× cap) and fixed
±1 sizing, gross and net (20bp/2bp round-trip), 70/30 IS/OOS with IS-only
selection, deflated Sharpe over all 1,508 configs.

**Headline (see `output/SUMMARY.md`):** the bands do mark continuation —
breakout is gross-positive at every N in every block and the fade is
negative everywhere — but the 50-SMA gate never beats the better single
piece, the ATR exit beats the structural channel exit everywhere, crypto
degrades gracefully OOS while futures collapse, and nothing survives the
deflated-Sharpe haircut or clearly beats buy & hold.

## Files

- `backtest.py` — full pipeline (download → state machines → report)
- `data/*.csv.gz` — committed OHLC snapshots (daily + 1h for the 4h check)
- `output/SUMMARY.md` — paste-ready report answering the six questions
- `output/results_all_configs.csv` — every config × {FULL, IS, OOS}

## Run

```bash
python -m venv .venv && .venv/bin/pip install -r ../intraday_sma/requirements.txt
.venv/bin/python backtest.py            # re-download (results drift with new data)
.venv/bin/python backtest.py --cached   # exact reproduction from the snapshot
```

Behind the TLS-reterminating proxy in this environment, `backtest.py`
automatically uses `curl_cffi` with `chrome110` impersonation and the
proxy CA bundle (`/root/.ccr/ca-bundle.crt`).
