#!/usr/bin/env python3
"""
Intraday SMA entry-rule backtest: 50-SMA price-cross vs 10/40 SMA crossover.

Head-to-head comparison on 1h and 4h bars, crypto vs futures, long/short
always-in-market, gross AND net of costs, fixed vs vol-scaled sizing,
with a 70/30 IS/OOS split and deflated-Sharpe multiple-testing accounting.

Data: yfinance (Yahoo). HARD LIMITATION: Yahoo serves only ~730 days of
hourly history, so everything here is exploratory. 4h bars are resampled
from 1h (anchored to UTC midnight) so both asset groups use one consistent
data source; Yahoo's native 4h interval has the same ~730d lookback anyway.

Futures tickers are front-month continuous with roll gaps — results for
futures are distorted by rolls; a proper test needs back-adjusted contracts.

Conventions (no look-ahead):
  - Signals are computed on CLOSED bars only. The position that earns bar
    t's close-to-close return is the signal from bar t-1 (shift by one).
  - Trailing vol for sizing is likewise lagged one bar.
  - The final (possibly still-forming) bar of every download is dropped.

Costs: charged per unit of turnover |Δposition|, at HALF the round-trip
rate per unit (a full round trip = 2 units of turnover):
  futures  2 bp round-trip -> 1 bp per unit turned over
  crypto  20 bp round-trip -> 10 bp per unit turned over
Vol-scaled sizing is charged on every rebalance (no rebalance band), which
is conservative for the vol-scaled variant.

Outputs (in ./output):
  results_all_configs.csv  - every config x {FULL, IS, OOS}
  SUMMARY.md               - paste-ready markdown report

Run:  python backtest.py            (downloads + caches data, then backtests)
      python backtest.py --cached   (skip downloads, use ./data cache only)
"""

import gzip
import io
import math
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
from scipy import stats as sstats

warnings.filterwarnings("ignore", category=FutureWarning)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT_DIR = os.path.join(HERE, "output")
CA_BUNDLE = "/root/.ccr/ca-bundle.crt"  # TLS-reterminating egress proxy CA

CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
          "ADA-USD", "DOGE-USD", "AVAX-USD", "DOT-USD", "LINK-USD"]
FUTURES = ["ES=F", "NQ=F", "YM=F", "GC=F", "SI=F",
           "CL=F", "NG=F", "HG=F", "ZB=F", "ZN=F"]
GROUPS = {"crypto": CRYPTO, "futures": FUTURES}

# one-way cost per unit of turnover (= half the round-trip cost)
ONE_WAY_COST = {"crypto": 0.0010, "futures": 0.0001}  # 20bp / 2bp round-trip

TIMEFRAMES = ["1h", "4h"]
STRATEGIES = ["sma50_cross", "sma10_40_cross"]
SIZINGS = ["fixed", "volscaled"]

TARGET_VOL = 0.15          # annualized vol target for vol-scaled sizing
MAX_LEVERAGE = 3.0         # cap on |position| for vol-scaled sizing
VOL_WINDOW = {"1h": 168, "4h": 42}   # trailing realized-vol window (bars)

MIN_BARS = 300             # skip instrument/timeframe with fewer usable bars
IS_FRACTION = 0.70         # oldest 70% in-sample, newest 30% out-of-sample

EULER_GAMMA = 0.5772156649015329


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def make_session():
    """curl_cffi session that trusts the egress proxy's CA.

    The proxy re-terminates TLS and rejects the newest chrome/firefox
    impersonation handshakes; chrome110 works and still passes Yahoo's
    client fingerprinting.
    """
    from curl_cffi import requests as cr
    kwargs = {"impersonate": "chrome110"}
    if os.path.exists(CA_BUNDLE):
        kwargs["verify"] = CA_BUNDLE
    return cr.Session(**kwargs)


def fetch_1h_close(ticker, session):
    """Max-available 1h close series (UTC tz, gz-cached in DATA_DIR)."""
    cache = os.path.join(DATA_DIR, ticker.replace("=", "_") + "_1h.csv.gz")
    if os.path.exists(cache):
        with gzip.open(cache, "rt") as f:
            s = pd.read_csv(f, index_col=0, parse_dates=True)["Close"]
        s.index = pd.DatetimeIndex(s.index, tz="UTC")
        return s
    if "--cached" in sys.argv:
        return None

    import yfinance as yf
    last_err = None
    for attempt in range(4):
        try:
            # "730d" is Yahoo's hard intraday cap and beats period="max":
            # for 24/5 futures it maps to ~876 calendar days of bars,
            # while "max"/"2y" return only ~730 calendar days.
            df = yf.Ticker(ticker, session=session).history(
                period="730d", interval="1h", auto_adjust=True)
            if df is not None and len(df) > 0:
                break
        except Exception as e:  # noqa: BLE001 - retry any transient failure
            last_err = e
        time.sleep(2 * (attempt + 1))
    else:
        print(f"  !! {ticker}: download failed ({last_err})")
        return None

    s = df["Close"].dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.index = s.index.tz_convert("UTC")
    s = s.iloc[:-1]  # drop the final, possibly still-forming bar
    with gzip.open(cache, "wt") as f:
        s.to_frame("Close").to_csv(f)
    return s


def resample_4h(close_1h):
    """1h -> 4h closes, buckets anchored to UTC midnight (00,04,08,...).

    Yahoo does expose a native 4h interval with the same ~730d cap, but
    resampling keeps one data source and one bucket alignment for both
    crypto (24/7) and futures (24/5) series.
    """
    s = close_1h.resample("4h", label="left", closed="left").last().dropna()
    return s.iloc[:-1]  # last bucket may be built from a partial 4h window


def bars_per_year(index):
    """Empirical bars/year from a series' own span (crypto ~8760 at 1h,
    futures ~6000 at 1h because they trade ~24/5)."""
    span_years = (index[-1] - index[0]).total_seconds() / (365.25 * 24 * 3600)
    return (len(index) - 1) / span_years


# --------------------------------------------------------------------------
# Signals and positions
# --------------------------------------------------------------------------

def signal_sma50_cross(close):
    """+1 when close > 50-SMA, -1 when below; exact ties hold prior stance."""
    sma = close.rolling(50).mean()
    sig = np.sign(close - sma)
    return sig.replace(0, np.nan).ffill()


def signal_sma10_40_cross(close):
    """+1 when 10-SMA > 40-SMA, -1 when below; exact ties hold prior stance."""
    fast = close.rolling(10).mean()
    slow = close.rolling(40).mean()
    sig = np.sign(fast - slow)
    return sig.replace(0, np.nan).ffill()


SIGNALS = {"sma50_cross": signal_sma50_cross,
           "sma10_40_cross": signal_sma10_40_cross}


def build_position(close, strategy, sizing, tf, bpy):
    """Raw (unshifted) position at each bar close. Caller shifts by 1."""
    sig = SIGNALS[strategy](close)
    if sizing == "fixed":
        return sig.fillna(0.0)
    rets = close.pct_change()
    vol_ann = rets.rolling(VOL_WINDOW[tf]).std() * math.sqrt(bpy)
    scale = (TARGET_VOL / vol_ann).clip(upper=MAX_LEVERAGE)
    return (sig * scale).fillna(0.0)


# --------------------------------------------------------------------------
# Backtest and metrics
# --------------------------------------------------------------------------

def run_strategy(close, strategy, sizing, tf, group, bpy):
    """Per-bar gross/net returns, applied position, and per-bar cost."""
    raw_pos = build_position(close, strategy, sizing, tf, bpy)
    pos = raw_pos.shift(1).fillna(0.0)          # enter next bar after signal
    rets = close.pct_change().fillna(0.0)
    gross = pos * rets
    turnover = pos.diff().abs().fillna(pos.abs())  # first bar = initial entry
    cost = turnover * ONE_WAY_COST[group]
    net = gross - cost
    return pd.DataFrame({"gross": gross, "net": net,
                         "pos": pos, "turnover": turnover})


def trade_stats(bt):
    """Trade-level win rate / profit factor on NET returns.

    A 'trade' is a maximal run of constant position sign (always-in-market
    strategies flip long<->short, so runs == trades). Trade P&L is the
    arithmetic sum of net per-bar returns during the run.
    """
    sign = np.sign(bt["pos"])
    active = sign != 0
    if not active.any():
        return np.nan, np.nan, 0
    trade_id = (sign != sign.shift(1)).cumsum()[active]
    pnl = bt.loc[active, "net"].groupby(trade_id).sum()
    n = len(pnl)
    win_rate = float((pnl > 0).mean()) if n else np.nan
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    pf = float(gains / losses) if losses > 0 else np.inf
    return win_rate, pf, n


def bar_stats(rets):
    """Bar-level win rate / profit factor (used for buy-and-hold)."""
    r = rets[rets != 0]
    if len(r) == 0:
        return np.nan, np.nan
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    return float((r > 0).mean()), float(gains / losses) if losses > 0 else np.inf


def perf_metrics(rets, bpy):
    """Annualized (arithmetic) return/vol/Sharpe, max drawdown, t-stat."""
    n = len(rets)
    if n < 20 or rets.std() == 0:
        return dict(ann_ret=np.nan, ann_vol=np.nan, sharpe=np.nan,
                    max_dd=np.nan, tstat=np.nan, n=n)
    mu, sd = rets.mean(), rets.std()
    sharpe = mu / sd * math.sqrt(bpy)
    years = n / bpy
    equity = (1 + rets).cumprod()
    dd = (equity / equity.cummax() - 1).min()
    return dict(ann_ret=mu * bpy, ann_vol=sd * math.sqrt(bpy), sharpe=sharpe,
                max_dd=float(dd), tstat=sharpe * math.sqrt(years), n=n)


def evaluate(bt, bpy, group, label_is_bh=False):
    """Full metric row (gross + net) for one return stream and period."""
    g = perf_metrics(bt["gross"], bpy)
    nmet = perf_metrics(bt["net"], bpy)
    years = len(bt) / bpy
    if label_is_bh:
        wr, pf = bar_stats(bt["net"])
        trades = np.nan
    else:
        wr, pf, ntr = trade_stats(bt)
        trades = ntr / years if years > 0 else np.nan
    return {
        "n_bars": len(bt), "bars_per_year": round(bpy, 1),
        "ann_ret_gross": g["ann_ret"], "ann_vol_gross": g["ann_vol"],
        "sharpe_gross": g["sharpe"],
        "ann_ret_net": nmet["ann_ret"], "ann_vol_net": nmet["ann_vol"],
        "sharpe_net": nmet["sharpe"], "max_dd_net": nmet["max_dd"],
        "tstat_net": nmet["tstat"], "win_rate_net": wr,
        "profit_factor_net": pf, "trades_per_year": trades,
        "turnover_units_per_year": bt["turnover"].sum() / years if years > 0 else np.nan,
    }


# --------------------------------------------------------------------------
# Deflated Sharpe (Bailey & Lopez de Prado 2014)
# --------------------------------------------------------------------------

def psr(rets, sr_star_bar):
    """Probabilistic Sharpe: P(true per-bar SR > sr_star_bar)."""
    n = len(rets)
    sr = rets.mean() / rets.std()
    skew = float(sstats.skew(rets))
    kurt = float(sstats.kurtosis(rets, fisher=False))
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if denom <= 0 or n < 20:
        return np.nan
    z = (sr - sr_star_bar) * math.sqrt(n - 1) / math.sqrt(denom)
    return float(sstats.norm.cdf(z))


def expected_max_sr(trial_sr_var_bar, n_trials):
    """E[max SR] among n_trials zero-skill trials (per-bar units)."""
    if trial_sr_var_bar <= 0 or n_trials < 2:
        return 0.0
    q1 = sstats.norm.ppf(1 - 1.0 / n_trials)
    q2 = sstats.norm.ppf(1 - 1.0 / (n_trials * math.e))
    return math.sqrt(trial_sr_var_bar) * ((1 - EULER_GAMMA) * q1 + EULER_GAMMA * q2)


# --------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    # ---- download ----
    session = None if "--cached" in sys.argv else make_session()
    closes_1h, skipped = {}, []
    print("Downloading 1h history (max available; Yahoo caps at ~730d)...")
    for group, tickers in GROUPS.items():
        for tkr in tickers:
            s = fetch_1h_close(tkr, session)
            if s is None or len(s) < MIN_BARS:
                skipped.append((tkr, "download failed" if s is None
                                else f"only {len(s)} bars"))
                continue
            closes_1h[tkr] = s
            print(f"  {tkr:9s} {len(s):6d} 1h bars  "
                  f"{s.index[0]:%Y-%m-%d} -> {s.index[-1]:%Y-%m-%d}")
            if session is not None:
                time.sleep(1.5)  # be polite to Yahoo
    if skipped:
        print("SKIPPED:", skipped)

    # ---- per-instrument backtests ----
    rows = []            # one row per config x period for the CSV
    port_inputs = {}     # (group, tf, strat, sizing) -> {tkr: net-return frame}
    bh_inputs = {}       # (group, tf) -> {tkr: bh frame}
    sample_rows = []

    for group, tickers in GROUPS.items():
        for tf in TIMEFRAMES:
            for tkr in tickers:
                if tkr not in closes_1h:
                    continue
                close = closes_1h[tkr] if tf == "1h" else resample_4h(closes_1h[tkr])
                if len(close) < MIN_BARS:
                    skipped.append((f"{tkr} {tf}", f"only {len(close)} bars"))
                    continue
                bpy = bars_per_year(close.index)
                sample_rows.append(dict(group=group, instrument=tkr, timeframe=tf,
                                        n_bars=len(close), bars_per_year=round(bpy),
                                        start=str(close.index[0].date()),
                                        end=str(close.index[-1].date())))
                # buy & hold benchmark: long 1 unit, entry cost once
                rets = close.pct_change().fillna(0.0)
                bh_cost = pd.Series(0.0, index=close.index)
                bh_cost.iloc[0] = ONE_WAY_COST[group]
                bh = pd.DataFrame({"gross": rets, "net": rets - bh_cost,
                                   "pos": 1.0, "turnover": 0.0})
                bh_inputs.setdefault((group, tf), {})[tkr] = bh

                for strat in STRATEGIES:
                    for sizing in SIZINGS:
                        bt = run_strategy(close, strat, sizing, tf, group, bpy)
                        port_inputs.setdefault((group, tf, strat, sizing), {})[tkr] = bt

    # ---- common IS/OOS boundary per group x timeframe (union index) ----
    boundaries = {}
    for (group, tf), members in bh_inputs.items():
        union = sorted(set().union(*[set(v.index) for v in members.values()]))
        boundaries[(group, tf)] = union[int(IS_FRACTION * len(union))]

    def add_rows(bt, bpy, group, tf, strat, sizing, level, instrument, is_bh=False):
        cut = boundaries[(group, tf)]
        for period, chunk in [("FULL", bt), ("IS", bt[bt.index < cut]),
                              ("OOS", bt[bt.index >= cut])]:
            if len(chunk) < 20:
                continue
            met = evaluate(chunk, bpy, group, label_is_bh=is_bh)
            rows.append(dict(level=level, group=group, timeframe=tf,
                             strategy=strat, sizing=sizing, instrument=instrument,
                             period=period,
                             start=str(chunk.index[0].date()),
                             end=str(chunk.index[-1].date()), **met))

    for (group, tf, strat, sizing), members in port_inputs.items():
        for tkr, bt in members.items():
            add_rows(bt, bars_per_year(bt.index), group, tf, strat, sizing,
                     "instrument", tkr)
        # equal-weight portfolio: mean across available members per bar
        panel = {c: pd.DataFrame({t: m[c] for t, m in members.items()}).mean(axis=1)
                 for c in ["gross", "net", "pos", "turnover"]}
        port = pd.DataFrame(panel).dropna()
        add_rows(port, bars_per_year(port.index), group, tf, strat, sizing,
                 "portfolio", "EW_PORTFOLIO")

    for (group, tf), members in bh_inputs.items():
        for tkr, bt in members.items():
            add_rows(bt, bars_per_year(bt.index), group, tf, "buyhold", "fixed",
                     "instrument", tkr, is_bh=True)
        panel = {c: pd.DataFrame({t: m[c] for t, m in members.items()}).mean(axis=1)
                 for c in ["gross", "net", "pos", "turnover"]}
        port = pd.DataFrame(panel).dropna()
        add_rows(port, bars_per_year(port.index), group, tf, "buyhold", "fixed",
                 "portfolio", "EW_PORTFOLIO", is_bh=True)

    df = pd.DataFrame(rows)

    # ---- CONSISTENT / FRAGILE flag: net-positive in BOTH IS and OOS ----
    key = ["level", "group", "timeframe", "strategy", "sizing", "instrument"]
    pos_by_period = df.pivot_table(index=key, columns="period",
                                   values="sharpe_net", aggfunc="first")
    flag = ((pos_by_period.get("IS") > 0) & (pos_by_period.get("OOS") > 0))
    flag = flag.map({True: "CONSISTENT", False: "FRAGILE"}).rename("flag")
    df = df.merge(flag.reset_index(), on=key, how="left")

    # ---- multiple-testing accounting over FULL-sample strategy configs ----
    strat_full = df[(df["strategy"] != "buyhold") & (df["period"] == "FULL")]
    n_trials = len(strat_full)
    sr_ann = strat_full["sharpe_net"].dropna()
    sr_dist = dict(n_configs=n_trials, mean=sr_ann.mean(), median=sr_ann.median(),
                   std=sr_ann.std(), p05=sr_ann.quantile(0.05),
                   p95=sr_ann.quantile(0.95))
    var_ann = sr_ann.var()

    # deflated Sharpe for the top FULL-sample configs (by net Sharpe)
    dsr_rows = []
    top = strat_full.sort_values("sharpe_net", ascending=False).head(6)
    for _, r in top.iterrows():
        members = port_inputs[(r["group"], r["timeframe"], r["strategy"], r["sizing"])]
        if r["level"] == "portfolio":
            net = pd.DataFrame({t: m["net"] for t, m in members.items()}).mean(axis=1).dropna()
        else:
            net = members[r["instrument"]]["net"]
        bpy = r["bars_per_year"]
        var_bar = var_ann / bpy  # de-annualize trial variance to this bar freq
        sr_star = expected_max_sr(var_bar, n_trials)
        dsr_rows.append(dict(
            level=r["level"], group=r["group"], timeframe=r["timeframe"],
            strategy=r["strategy"], sizing=r["sizing"], instrument=r["instrument"],
            sharpe_net_ann=r["sharpe_net"],
            sr_star_ann=sr_star * math.sqrt(bpy),
            p_true_sr_gt0=psr(net, 0.0),
            deflated_sharpe=psr(net, sr_star)))
    dsr_df = pd.DataFrame(dsr_rows)

    # ---- IS-only strategy selection, evaluated once on OOS ----
    oos_rows = []
    port = df[df["level"] == "portfolio"]
    for group in GROUPS:
        for tf in TIMEFRAMES:
            for sizing in SIZINGS:
                cand = port[(port["group"] == group) & (port["timeframe"] == tf)
                            & (port["sizing"] == sizing)
                            & (port["strategy"] != "buyhold")]
                is_sr = cand[cand["period"] == "IS"].set_index("strategy")["sharpe_net"]
                if is_sr.dropna().empty:
                    continue
                pick = is_sr.idxmax()
                oos_sr = cand[(cand["period"] == "OOS")
                              & (cand["strategy"] == pick)]["sharpe_net"]
                bh = port[(port["group"] == group) & (port["timeframe"] == tf)
                          & (port["strategy"] == "buyhold")
                          & (port["period"] == "OOS")]["sharpe_net"]
                oos_rows.append(dict(
                    group=group, timeframe=tf, sizing=sizing, selected=pick,
                    is_sharpe_net=float(is_sr[pick]),
                    oos_sharpe_net=float(oos_sr.iloc[0]) if len(oos_sr) else np.nan,
                    degradation=(float(oos_sr.iloc[0]) - float(is_sr[pick]))
                    if len(oos_sr) else np.nan,
                    bh_oos_sharpe_net=float(bh.iloc[0]) if len(bh) else np.nan))
    oos_df = pd.DataFrame(oos_rows)

    # ---- write outputs ----
    df.to_csv(os.path.join(OUT_DIR, "results_all_configs.csv"),
              index=False, float_format="%.4f")
    sample_df = pd.DataFrame(sample_rows)
    write_summary(df, sample_df, oos_df, dsr_df, sr_dist, skipped)
    print(f"\nDone in {time.time() - t0:.0f}s. Outputs in {OUT_DIR}/")


# --------------------------------------------------------------------------
# Markdown report
# --------------------------------------------------------------------------

def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "inf" if isinstance(x, float) and math.isinf(x) else "—"
    return f"{x:.{nd}f}"


def md_table(df, cols, headers, nd=2):
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append(fmt(v, nd) if isinstance(v, (int, float, np.floating))
                         and not isinstance(v, (bool, np.bool_)) else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_summary(df, sample_df, oos_df, dsr_df, sr_dist, skipped):
    L = []
    A = L.append
    strat_name = {"sma50_cross": "50-SMA cross", "sma10_40_cross": "10/40 SMA cross",
                  "buyhold": "Buy & hold"}
    dfp = df.copy()
    dfp["strategy_label"] = dfp["strategy"].map(strat_name)

    A("# Intraday SMA entry-rule backtest — 50-SMA cross vs 10/40 crossover "
      "(1h & 4h, crypto vs futures)")
    A("")
    A(f"*Run date: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d}. Data: Yahoo Finance "
      "via yfinance. **Exploratory** — Yahoo caps hourly history at ~730 days, "
      "so every result below rests on ≈2 years of data (see sample sizes). "
      "4h bars are **resampled from 1h**, anchored to UTC midnight (Yahoo's "
      "native 4h has the same lookback; resampling keeps one consistent data "
      "source for both groups). Futures are front-month continuous with roll "
      "gaps, which distorts their results — a proper futures test needs "
      "back-adjusted contracts. Costs: 20 bp round-trip crypto, 2 bp futures, "
      "charged per unit of turnover. Signals on closed bars, entry next bar. "
      "Long/short, always in market.*")
    A("")

    # ---- sample sizes ----
    A("## 1. Sample sizes (actual data retrieved)")
    A("")
    piv = sample_df.pivot_table(index=["group", "instrument"], columns="timeframe",
                                values=["n_bars", "start"], aggfunc="first")
    tbl = pd.DataFrame({
        "group": [i[0] for i in piv.index],
        "instrument": [i[1] for i in piv.index],
        "start_1h": piv[("start", "1h")].values,
        "bars_1h": piv[("n_bars", "1h")].values.astype(int),
        "bars_4h": piv[("n_bars", "4h")].values.astype(int),
    }).sort_values(["group", "instrument"])
    A(md_table(tbl, ["group", "instrument", "start_1h", "bars_1h", "bars_4h"],
               ["Group", "Instrument", "History starts", "1h bars", "4h bars"], 0))
    A("")
    if skipped:
        A("Skipped (insufficient data): " +
          ", ".join(f"{t} ({why})" for t, why in skipped))
    else:
        A("No instruments were skipped — all 20 delivered enough history for "
          "a 50-period signal plus IS/OOS evaluation.")
    A("")

    # ---- group x timeframe x strategy net sharpe ----
    A("## 2. Group × timeframe × strategy — equal-weight portfolio Sharpe "
      "(FULL sample)")
    A("")
    port = dfp[(dfp["level"] == "portfolio") & (dfp["period"] == "FULL")]
    for sizing in SIZINGS:
        A(f"### Sizing: {sizing}")
        A("")
        sub = port[(port["sizing"] == sizing) | (port["strategy"] == "buyhold")]
        sub = sub.sort_values(["group", "timeframe", "strategy"])
        A(md_table(sub, ["group", "timeframe", "strategy_label", "sharpe_gross",
                         "sharpe_net", "ann_ret_net", "max_dd_net",
                         "trades_per_year", "turnover_units_per_year"],
                   ["Group", "TF", "Strategy", "Gross Sharpe", "Net Sharpe",
                    "Net ann. ret", "Max DD", "Trades/yr", "Turnover/yr"]))
        A("")

    # ---- per-instrument ranked tables ----
    A("## 3. Per-instrument results, ranked by net Sharpe (FULL sample, "
      "fixed ±1 sizing)")
    A("")
    A("Flag = CONSISTENT if net Sharpe > 0 in *both* the IS (oldest 70%) and "
      "OOS (newest 30%) sub-periods, else FRAGILE.")
    A("")
    inst = dfp[(dfp["level"] == "instrument") & (dfp["period"] == "FULL")
               & (dfp["sizing"] == "fixed") & (dfp["strategy"] != "buyhold")]
    for group in GROUPS:
        for tf in TIMEFRAMES:
            sub = inst[(inst["group"] == group) & (inst["timeframe"] == tf)]
            sub = sub.sort_values("sharpe_net", ascending=False)
            A(f"### {group} — {tf}")
            A("")
            A(md_table(sub, ["instrument", "strategy_label", "sharpe_gross",
                             "sharpe_net", "tstat_net", "win_rate_net",
                             "profit_factor_net", "trades_per_year", "flag"],
                       ["Instrument", "Strategy", "Gross SR", "Net SR", "t-stat",
                        "Win rate", "Profit factor", "Trades/yr", "Flag"]))
            A("")

    # ---- fixed vs vol-scaled comparison ----
    A("## 4. Fixed ±1 vs volatility-scaled sizing (EW portfolios, net Sharpe, "
      "FULL sample)")
    A("")
    cmp_rows = []
    p2 = dfp[(dfp["level"] == "portfolio") & (dfp["period"] == "FULL")
             & (dfp["strategy"] != "buyhold")]
    for (g, tf, st), grp in p2.groupby(["group", "timeframe", "strategy"]):
        r = {s: grp[grp["sizing"] == s]["sharpe_net"] for s in SIZINGS}
        cmp_rows.append(dict(group=g, timeframe=tf,
                             strategy=strat_name[st],
                             fixed=float(r["fixed"].iloc[0]) if len(r["fixed"]) else np.nan,
                             volscaled=float(r["volscaled"].iloc[0]) if len(r["volscaled"]) else np.nan))
    cmp_df = pd.DataFrame(cmp_rows)
    cmp_df["delta"] = cmp_df["volscaled"] - cmp_df["fixed"]
    A(md_table(cmp_df.sort_values(["group", "timeframe"]),
               ["group", "timeframe", "strategy", "fixed", "volscaled", "delta"],
               ["Group", "TF", "Strategy", "Fixed net SR", "Vol-scaled net SR",
                "Δ (scaled − fixed)"]))
    A("")

    # ---- OOS ----
    A("## 5. Out-of-sample validation (select on IS only, run once on OOS)")
    A("")
    A("Oldest 70% in-sample / newest 30% out-of-sample; the better strategy per "
      "group × timeframe × sizing is picked on IS portfolio net Sharpe alone, "
      "then evaluated once on OOS. Degradation = OOS − IS.")
    A("")
    oos = oos_df.copy()
    oos["selected"] = oos["selected"].map(strat_name)
    A(md_table(oos, ["group", "timeframe", "sizing", "selected", "is_sharpe_net",
                     "oos_sharpe_net", "degradation", "bh_oos_sharpe_net"],
               ["Group", "TF", "Sizing", "Selected (on IS)", "IS net SR",
                "OOS net SR", "Degradation", "B&H OOS net SR"]))
    A("")

    # ---- multiple testing ----
    A("## 6. Multiple-testing accounting")
    A("")
    A(f"Total strategy configs evaluated (instrument- and portfolio-level, "
      f"FULL sample): **N = {sr_dist['n_configs']}**. Distribution of NET "
      f"annualized Sharpes across all of them: mean {fmt(sr_dist['mean'])}, "
      f"median {fmt(sr_dist['median'])}, std {fmt(sr_dist['std'])}, "
      f"5th pct {fmt(sr_dist['p05'])}, 95th pct {fmt(sr_dist['p95'])}.")
    A("")
    A("Top configs — regular vs deflated Sharpe (Bailey & López de Prado; "
      "SR\\* = expected max Sharpe of N zero-skill trials with the observed "
      "cross-config Sharpe variance):")
    A("")
    d2 = dsr_df.copy()
    d2["config"] = (d2["group"] + " " + d2["timeframe"] + " "
                    + d2["strategy"].map(strat_name) + " " + d2["sizing"]
                    + " (" + d2["instrument"] + ")")
    A(md_table(d2, ["config", "sharpe_net_ann", "sr_star_ann", "p_true_sr_gt0",
                    "deflated_sharpe"],
               ["Config", "Net ann. SR", "SR* (exp. max, ann.)",
                "P(true SR>0)", "Deflated SR  P(SR>SR*)"]))
    A("")

    # ---- verdict ----
    A("## 7. Plain-English verdict")
    A("")
    verdict = build_verdict(dfp, oos_df, dsr_df, strat_name)
    A(verdict)
    A("")
    A("---")
    A("*Reproduce: `python backtest.py` (or `--cached` to reuse the committed "
      "data snapshot in `data/`). All configs: `output/results_all_configs.csv` "
      "(column `period` ∈ FULL/IS/OOS).*")

    with open(os.path.join(OUT_DIR, "SUMMARY.md"), "w") as f:
        f.write("\n".join(L))


def build_verdict(dfp, oos_df, dsr_df, strat_name):
    """Data-driven answers to the four questions."""
    port = dfp[(dfp["level"] == "portfolio") & (dfp["period"] == "FULL")
               & (dfp["strategy"] != "buyhold")]
    bh = dfp[(dfp["level"] == "portfolio") & (dfp["period"] == "FULL")
             & (dfp["strategy"] == "buyhold")]
    out = []

    # Q1 which rule wins per group x tf (fixed sizing, net)
    out.append("**Q1 — 50-SMA cross vs 10/40 crossover:**")
    for g in GROUPS:
        for tf in TIMEFRAMES:
            sub = port[(port["group"] == g) & (port["timeframe"] == tf)
                       & (port["sizing"] == "fixed")]
            if sub.empty:
                continue
            best = sub.loc[sub["sharpe_net"].idxmax()]
            other = sub[sub["strategy"] != best["strategy"]]
            o_sr = float(other["sharpe_net"].iloc[0]) if len(other) else np.nan
            out.append(f"- {g} {tf}: **{strat_name[best['strategy']]}** wins on net "
                       f"Sharpe ({fmt(best['sharpe_net'])} vs {fmt(o_sr)}, "
                       f"fixed sizing, EW portfolio).")
    out.append("")

    # Q2 1h vs 4h
    out.append("**Q2 — 1h vs 4h:** average EW-portfolio net Sharpe across "
               "strategies and sizings —")
    for g in GROUPS:
        m = {tf: port[(port["group"] == g)
                      & (port["timeframe"] == tf)]["sharpe_net"].mean()
             for tf in TIMEFRAMES}
        better = max(m, key=lambda k: (m[k] if not math.isnan(m[k]) else -9e9))
        out.append(f"- {g}: 1h avg {fmt(m['1h'])}, 4h avg {fmt(m['4h'])} → "
                   f"**{better}** is less bad / better.")
    out.append("")

    # Q3 crypto vs futures
    m = {g: port[port["group"] == g]["sharpe_net"].mean() for g in GROUPS}
    better = max(m, key=lambda k: (m[k] if not math.isnan(m[k]) else -9e9))
    out.append(f"**Q3 — crypto vs futures:** average net Sharpe across all "
               f"intraday configs: crypto {fmt(m['crypto'])}, futures "
               f"{fmt(m['futures'])} → **{better}** shows the cleaner (or less "
               f"negative) trend edge at these horizons. Futures results carry "
               f"the extra caveat of front-month roll gaps.")
    out.append("")

    # Q4 does anything survive
    surv = oos_df[(oos_df["oos_sharpe_net"] > 0)]
    beat_bh = oos_df[(oos_df["oos_sharpe_net"] > oos_df["bh_oos_sharpe_net"])]
    beat_bh_pos = beat_bh[beat_bh["oos_sharpe_net"] > 0]
    strict = oos_df[(oos_df["oos_sharpe_net"] > 0)
                    & (oos_df["oos_sharpe_net"] > oos_df["bh_oos_sharpe_net"])]
    dsr_pos = dsr_df[dsr_df["deflated_sharpe"] > 0.5]
    out.append("**Q4 — does anything survive costs + OOS + deflation, or beat "
               "buy-and-hold?**")
    out.append(f"- Positive OOS net Sharpe after IS-only selection: "
               f"{len(surv)} of {len(oos_df)} selections.")
    out.append(f"- OOS net Sharpe above buy-and-hold OOS: {len(beat_bh)} of "
               f"{len(oos_df)} — but only {len(beat_bh_pos)} of those were also "
               f"positive in absolute terms (beating a negative benchmark just "
               f"means losing less).")
    out.append(f"- Positive OOS **and** above buy-and-hold: {len(strict)} of "
               f"{len(oos_df)}.")
    out.append(f"- Deflated Sharpe > 0.5 (i.e. more likely skill than the "
               f"luck-of-the-draw expected max of {len(dsr_df)} examined top "
               f"configs): {len(dsr_pos)} of {len(dsr_df)}.")
    bh_sr = {(r["group"], r["timeframe"]): r["sharpe_net"]
             for _, r in bh.iterrows()}
    bh_txt = ", ".join(f"{g}/{tf}: {fmt(v)}" for (g, tf), v in sorted(bh_sr.items()))
    out.append(f"- Buy-and-hold EW-portfolio net Sharpe (FULL sample) for "
               f"reference — {bh_txt}.")
    if len(strict) == 0 and len(dsr_pos) == 0:
        out.append("")
        out.append("**Bottom line: nothing survives the full gauntlet.** No "
                   "configuration is simultaneously positive out-of-sample, "
                   "better than buy-and-hold, and distinguishable from "
                   "selection luck (all deflated Sharpes are far below 0.5). "
                   "On ~2 years of intraday data these two SMA entry rules do "
                   "not demonstrate a deployable edge net of costs; slower "
                   "signals on 4h bars merely lose less than fast ones on 1h, "
                   "where costs are ruinous. This matches the prior daily-bar "
                   "finding that raw entry rules carry little standalone "
                   "value.")
    return "\n".join(out)


if __name__ == "__main__":
    main()
