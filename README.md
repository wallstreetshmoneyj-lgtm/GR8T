# GR8T — strategy backtester

A backtesting sandbox for a top-down **trend → point-of-interest → entry**
trading strategy, built to test and refine the rules before wiring them into an
autonomous bot.

It pulls 5-minute candles, resamples them to 15m and 1h, evaluates every bar
for the full setup (with no look-ahead), simulates the dynamic ATR-trailed risk
model, and reports the statistics. A web UI charts the candles, the 50 SMA, the
imbalance zones, and every trade — click any trade to see its POI box, entry,
stop, exit and POC drawn on the chart.

---

## The strategy, as implemented

The rules are applied strictly in order: **trend, then POI, then entry.**

### 1. Trend — 50 SMA confluence
On each timeframe, `close > 50 SMA` is **bullish**, `close < 50 SMA` is
**bearish**. A trade is only allowed when **all three timeframes (1h, 15m, 5m)
agree**. Higher-timeframe trend is mapped onto each 5m bar using only the most
recently *completed* HTF bar (an as-of join on bar close times), so there is no
look-ahead.

### 2. Point of interest — multi-timeframe imbalance
An **imbalance** (fair value gap) is a 3-candle pattern where:
- all three candles are the **same colour** (matching the trend direction), and
- there is a real **gap**: bullish ⇒ `candle3.low > candle1.high`; bearish ⇒
  `candle3.high < candle1.low`.

The gap zone is `[candle1.high, candle3.low]` (bullish) and it only becomes
usable once candle 3 has closed and price later **returns** into it.

A POI must be **multi-timeframe**: the imbalance has to overlap an imbalance on
a *different* timeframe (e.g. a 1h imbalance with a 15m imbalance nested inside).

When several qualifying imbalances are tapped at once, the **POC tie-breaker**
picks the one whose midpoint is closest to the **point of control** of a 15m
**volume profile** built over the **current structure leg** — defined as the span
from the most recent confirmed swing low ↔ swing high (configurable pivot
strength). If the instrument reports no volume (e.g. a cash index), it falls
back to the zone nearest current price.

### 3. Entry — 5m candle pattern
Once price is inside the POI **and** trend confluence holds, the 5m bar must
complete a trend-aligned pattern:
- bullish ⇒ **bullish engulfing** or **hammer**
- bearish ⇒ **bearish engulfing** or **shooting star**

Entry is taken at the close of the signal candle.

### Risk — dynamic ATR trail
- **Initial stop** at the far edge of the POI (or the signal candle), with an
  optional ATR buffer. `1R` = entry-to-stop distance.
- At **1:1** the stop moves to **break-even**.
- After break-even the stop **trails by `ATR × multiplier`** behind each new
  *closed* high (long) / low (short) — a new extreme is only recognised once the
  candle closes, exactly as specified.

Intrabar assumptions are conservative: the stop is checked before the target,
a level moved on a bar only takes effect from the next bar, and gaps through the
stop fill at the bar open.

---

## Quick start

```bash
pip install -r requirements.txt

# command-line backtest
python -m gr8t.cli --symbol SPY --preset intraday     # 5m/15m/1h, ~60 days
python -m gr8t.cli --symbol SPY --preset swing        # 1h/4h/1d, ~2 years
python -m gr8t.cli --symbol NQ=F --preset swing --atr-mult 1.5 --stop-mode signal
python -m gr8t.cli --symbol SPY --preset swing --report spy.html   # visual report
python -m gr8t.cli --synthetic                        # offline, deterministic demo

# web UI  ->  http://127.0.0.1:5000
python webui/run.py
```

### Historical depth (presets)

The strategy logic is identical at every scale; only the base timeframe — and
therefore how much history Yahoo will serve — changes:

| Preset     | Timeframes    | History  | Use                                 |
| :--------- | :------------ | :------- | :---------------------------------- |
| `intraday` | 5m / 15m / 1h | ~60 days | the real intraday strategy          |
| `swing`    | 1h / 4h / 1d  | ~2 years | same rules, multi-year track record |

Yahoo caps 5m history at ~60 days, so `intraday` is the deepest the real
strategy goes on the free feed; `swing` runs the same rules on an hourly base
for a ~2-year backtest. Requested ranges are auto-clamped to what each interval
allows. Data comes from a dependency-light Yahoo `requests` client (proxy-
friendly), cached for an hour under `data_cache/`.

### Visual report

`--report PATH` (CLI) or the **Download HTML report** button (web UI) writes a
self-contained dashboard — stat cards, equity curve, underwater drawdown,
per-trade R, R-multiple distribution, monthly R, and the full trade ledger — as
a single HTML file with no JavaScript or external dependencies, so it opens and
shares anywhere.

Good symbols to try: `SPY`, `QQQ`, `ES=F`, `NQ=F`, `AAPL`, `NVDA`. Futures and
single stocks carry real volume (so the POC tie-breaker is active); cash indices
like `^GSPC` do not.

---

## Web UI

- Pick a **mode** (`intraday` or `swing`) and a symbol, tune any parameter, and
  **Run backtest**.
- The chart shows candles, the 50 SMA, and ▲/▼ entry + ● exit markers.
- **Click any row** in the trades table to draw that trade's POI zone, entry,
  stop, exit, and POC, and zoom the chart to it.
- The **Visual stats** panel (equity, drawdown, per-trade R, R distribution,
  monthly R) and the performance detail update on every run.
- **Download HTML report** saves the self-contained dashboard for the current
  settings.

---

## Project layout

```
gr8t/
  config.py      every tunable parameter (one dataclass, dict round-trips)
  data.py        Yahoo client, resampling, no-look-ahead MTF alignment, synthetic data
  indicators.py  SMA, ATR, swing pivots, volume profile / POC, current leg
  patterns.py    imbalance detection + engulfing / hammer / shooting-star
  strategy.py    trend → POI → entry signal generation (no look-ahead)
  backtest.py    position + ATR-trail risk engine, equity curve
  stats.py       win rate, expectancy, profit factor, drawdown, …
  cli.py         command-line runner
webui/
  app.py         Flask API (/api/backtest) + page
  run.py         launcher
  static/, templates/   lightweight-charts front-end (vendored, no CDN)
tests/
  test_core.py   11 unit tests: indicators, imbalances, patterns, risk engine
```

Run the tests with `python -m pytest -q`.

---

## Judgement calls worth revisiting

These were under-specified by the rules; each is configurable in `Config` so we
can tune them together:

- **POI tap** = price overlapping the zone with any part of the bar. Could
  instead require the candle body, or a close inside the zone.
- **Initial stop** defaults to the POI edge + 0.1 ATR. `--stop-mode signal`
  uses the signal candle instead.
- **Which zone is "the POI"** when nested: currently whichever imbalance the POC
  selects, of any timeframe. We could force the higher-timeframe zone.
- **Current structure leg** uses fractal pivots of strength `swing_lookback`.
- **One position at a time**; new signals are ignored while a trade is open.
- **Costs/slippage** are off by default (`cost_per_trade_r`).

## Limitations / next steps

- 5m history is limited to ~60 days by the free Yahoo feed; a paid provider
  (Polygon/Alpaca/Databento) would unlock longer, cleaner backtests.
- No session/overnight-gap handling yet (fine for 24h futures; RTH equities
  resample by calendar).
- Toward autonomous trading: the `Strategy.evaluate(i)` signal interface is the
  natural seam to feed a live broker/exchange adapter, reusing the exact same
  rules this backtester validates.

*For research and education. Not financial advice.*
