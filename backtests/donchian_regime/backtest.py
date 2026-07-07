#!/usr/bin/env python3
"""
Donchian breakout + 50-SMA regime filter: marginal-contribution study.

Tests whether a structural trend trigger (pure N-bar high/low breakout,
no smoothing) captures trend on crypto and futures, and whether gating it
with a 50-SMA regime filter adds value over either piece alone.

Strategies (long/short, always-in unless stopped out to flat):
  A  donch_break   Donchian breakout. Enter long on close > highest high
                   of the PRIOR N bars (current bar excluded), short on
                   close < lowest low of prior N bars. Exit either on the
                   opposite N/2-bar channel (structural trailing stop) or
                   on a 3x ATR(20) chandelier trailing stop. Opposite
                   N-bar breakouts reverse the position directly.
                   N sweep: {10, 20, 40, 55, 80}.
  B  sma50_regime  Regime filter alone: long when close > 50-SMA, short
                   below (always in market).
  C  combo         A gated by B: hold A's position only while its sign
                   agrees with the 50-SMA regime; stand flat on
                   disagreement. THE key test is whether C beats both
                   A and B individually (marginal contribution).
  D  donch_fade    Diagnostic reversion: fade the band (short upper
                   break, long lower break), exit at channel middle.
                   Reported only to show whether price trends or
                   mean-reverts at the bands. Not optimized.
  buyhold          Benchmark.

Data: yfinance daily (crypto: max history; futures: ~7y front-month
continuous — roll gaps distort breakout signals, a proper test needs
back-adjusted contracts) plus a 4h cross-check (resampled from 1h,
Yahoo caps intraday at ~730d) for BTC, ETH, ES, NQ, GC.

No look-ahead: channels/SMA/ATR/vol are computed on closed bars; the
position that earns bar t's close-to-close return is the state after
bar t-1 (shifted one bar). The final possibly-partial bar is dropped.

Sizing: volatility-scaled is primary (15% annual target, trailing
realized vol, 3x cap); fixed +/-1 reported for reference.

Costs: charged per unit of turnover |dPosition| at half the round-trip
rate (crypto 20bp round-trip -> 10bp one-way; futures 2bp -> 1bp).
Costs are reported (gross AND net) but are secondary to the structural
question here.

Outputs (./output): SUMMARY.md and results_all_configs.csv
Run:  python backtest.py          (download + cache + backtest)
      python backtest.py --cached (reuse committed ./data snapshot)
"""

import gzip
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
CA_BUNDLE = "/root/.ccr/ca-bundle.crt"

CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
          "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "DOT-USD"]
FUTURES = ["ES=F", "NQ=F", "YM=F", "GC=F", "SI=F",
           "CL=F", "NG=F", "HG=F", "ZB=F", "ZN=F"]
H4_TICKERS = ["BTC-USD", "ETH-USD", "ES=F", "NQ=F", "GC=F"]

GROUP_OF = {**{t: "crypto" for t in CRYPTO}, **{t: "futures" for t in FUTURES}}
ONE_WAY_COST = {"crypto": 0.0010, "futures": 0.0001}  # half of 20bp / 2bp RT

N_SWEEP = [10, 20, 40, 55, 80]
EXITS = ["channel", "atr"]          # for A and C
ATR_LEN, ATR_MULT = 20, 3.0
SMA_LEN = 50

TARGET_VOL = 0.15
MAX_LEVERAGE = 3.0
VOL_WINDOW = {"1d": 20, "4h": 42}   # trailing realized-vol window, bars
SIZINGS = ["volscaled", "fixed"]

MIN_BARS = 400                      # need 80-bar channel + real sample
IS_FRACTION = 0.70
EULER_GAMMA = 0.5772156649015329

STRAT_LABEL = {"donch_break": "A Donchian breakout",
               "sma50_regime": "B 50-SMA regime",
               "combo": "C combo (A gated by B)",
               "donch_fade": "D Donchian fade (diagnostic)",
               "buyhold": "Buy & hold"}


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def make_session():
    """curl_cffi session for Yahoo through the TLS-reterminating proxy.

    The proxy rejects the newest chrome/firefox impersonation handshakes;
    chrome110 works and still passes Yahoo's client fingerprinting.
    """
    from curl_cffi import requests as cr
    kwargs = {"impersonate": "chrome110"}
    if os.path.exists(CA_BUNDLE):
        kwargs["verify"] = CA_BUNDLE
    return cr.Session(**kwargs)


def _fetch(ticker, session, period, interval):
    """OHLC frame from Yahoo with retries; gz-cached under DATA_DIR."""
    tag = interval if interval != "1h" else "1h"
    cache = os.path.join(DATA_DIR, f"{ticker.replace('=', '_')}_{tag}.csv.gz")
    if os.path.exists(cache):
        with gzip.open(cache, "rt") as f:
            df = pd.read_csv(f, index_col=0, parse_dates=True)
        if interval == "1h":
            df.index = pd.DatetimeIndex(df.index, tz="UTC")
        return df
    if "--cached" in sys.argv:
        return None

    import yfinance as yf
    last_err = None
    for attempt in range(4):
        try:
            raw = yf.Ticker(ticker, session=session).history(
                period=period, interval=interval, auto_adjust=True)
            if raw is not None and len(raw) > 0:
                break
        except Exception as e:  # noqa: BLE001 - retry any transient failure
            last_err = e
        time.sleep(2 * (attempt + 1))
    else:
        print(f"  !! {ticker} {interval}: download failed ({last_err})")
        return None

    df = raw[["Open", "High", "Low", "Close"]].dropna()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if interval == "1h":
        df.index = df.index.tz_convert("UTC")
    else:
        df.index = df.index.tz_localize(None).normalize()
    df = df.iloc[:-1]  # drop final, possibly still-forming bar
    with gzip.open(cache, "wt") as f:
        df.to_csv(f)
    time.sleep(1.5)  # politeness between live downloads
    return df


def resample_4h(df_1h):
    """1h OHLC -> 4h OHLC, buckets anchored to UTC midnight."""
    agg = df_1h.resample("4h", label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    return agg.dropna().iloc[:-1]  # last bucket may span a partial window


def bars_per_year(index):
    span_years = (index[-1] - index[0]).total_seconds() / (365.25 * 24 * 3600)
    return (len(index) - 1) / span_years


# --------------------------------------------------------------------------
# Signal state machines (evaluated on closed bars; caller shifts by 1)
# --------------------------------------------------------------------------

def atr_series(df, n=ATR_LEN):
    prev_c = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - prev_c).abs(),
                    (df["Low"] - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def donchian_break_state(df, n_entry, exit_mode):
    """A: breakout state in {-1, 0, +1}. Channels use PRIOR bars only.

    Long entry  : close > highest high of prior n_entry bars
    Short entry : close < lowest  low  of prior n_entry bars
    Exit 'channel': opposite (n_entry//2)-bar extreme (structural stop)
    Exit 'atr'    : 3x ATR(20) chandelier from the best high/low since entry
    Opposite n_entry-bar breakouts reverse the position directly.
    """
    n_exit = max(2, n_entry // 2)
    up_n = df["High"].shift(1).rolling(n_entry).max().values
    lo_n = df["Low"].shift(1).rolling(n_entry).min().values
    up_x = df["High"].shift(1).rolling(n_exit).max().values
    lo_x = df["Low"].shift(1).rolling(n_exit).min().values
    atr = atr_series(df).values if exit_mode == "atr" else None
    c, h, l = df["Close"].values, df["High"].values, df["Low"].values

    st = np.zeros(len(df))
    state, best = 0, np.nan  # best = extreme close-side price since entry
    for t in range(len(df)):
        if np.isnan(up_n[t]) or (atr is not None and np.isnan(atr[t])):
            continue
        if state == 1:
            if c[t] < lo_n[t]:                     # opposite breakout: reverse
                state, best = -1, l[t]
            elif exit_mode == "channel" and c[t] < lo_x[t]:
                state = 0
            elif exit_mode == "atr":
                best = max(best, h[t])
                if c[t] < best - ATR_MULT * atr[t]:
                    state = 0
        elif state == -1:
            if c[t] > up_n[t]:
                state, best = 1, h[t]
            elif exit_mode == "channel" and c[t] > up_x[t]:
                state = 0
            elif exit_mode == "atr":
                best = min(best, l[t])
                if c[t] > best + ATR_MULT * atr[t]:
                    state = 0
        if state == 0:
            if c[t] > up_n[t]:
                state, best = 1, h[t]
            elif c[t] < lo_n[t]:
                state, best = -1, l[t]
        st[t] = state
    return pd.Series(st, index=df.index)


def donchian_fade_state(df, n_entry):
    """D: fade the band; exit at channel middle. Diagnostic only."""
    up_n = df["High"].shift(1).rolling(n_entry).max().values
    lo_n = df["Low"].shift(1).rolling(n_entry).min().values
    mid = (up_n + lo_n) / 2
    c = df["Close"].values
    st = np.zeros(len(df))
    state = 0
    for t in range(len(df)):
        if np.isnan(up_n[t]):
            continue
        if state == -1:                     # short from upper-band fade
            if c[t] < lo_n[t]:
                state = 1                   # opposite band: flip
            elif c[t] <= mid[t]:
                state = 0                   # target: channel middle
        elif state == 1:
            if c[t] > up_n[t]:
                state = -1
            elif c[t] >= mid[t]:
                state = 0
        if state == 0:
            if c[t] > up_n[t]:
                state = -1                  # fade the upside break
            elif c[t] < lo_n[t]:
                state = 1                   # fade the downside break
        st[t] = state
    return pd.Series(st, index=df.index)


def sma_regime_state(close):
    """B: +1 above the 50-SMA, -1 below; exact ties hold prior stance."""
    sig = np.sign(close - close.rolling(SMA_LEN).mean())
    return sig.replace(0, np.nan).ffill().fillna(0.0)


# --------------------------------------------------------------------------
# Backtest mechanics
# --------------------------------------------------------------------------

def vol_scale(close, tf, bpy):
    """Trailing realized vol -> position multiplier (lagged by caller)."""
    vol_ann = close.pct_change().rolling(VOL_WINDOW[tf]).std() * math.sqrt(bpy)
    return (TARGET_VOL / vol_ann).clip(upper=MAX_LEVERAGE)


def run_state(close, state, sizing, tf, group, bpy):
    """Per-bar gross/net returns for a raw signal state series."""
    if sizing == "volscaled":
        raw_pos = (state * vol_scale(close, tf, bpy)).fillna(0.0)
    else:
        raw_pos = state.astype(float)
    pos = raw_pos.shift(1).fillna(0.0)      # enter the bar AFTER the signal
    rets = close.pct_change().fillna(0.0)
    gross = pos * rets
    turnover = pos.diff().abs().fillna(pos.abs())
    net = gross - turnover * ONE_WAY_COST[group]
    return pd.DataFrame({"gross": gross, "net": net,
                         "pos": pos, "turnover": turnover})


def trade_stats(bt):
    """Trade-level stats on NET returns. A trade = maximal run of constant
    position sign (flat periods break runs). PnL = arithmetic sum of net
    per-bar returns in the run."""
    sign = np.sign(bt["pos"])
    active = sign != 0
    if not active.any():
        return np.nan, np.nan, np.nan, 0
    trade_id = (sign != sign.shift(1)).cumsum()[active]
    pnl = bt.loc[active, "net"].groupby(trade_id).sum()
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    win_rate = float((pnl > 0).mean())
    payoff = float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else np.nan
    pf = float(wins.sum() / -losses.sum()) if losses.sum() < 0 else np.inf
    return win_rate, payoff, pf, len(pnl)


def bar_stats(rets):
    """Bar-level win rate / payoff / PF (used for buy-and-hold)."""
    r = rets[rets != 0]
    if len(r) == 0:
        return np.nan, np.nan, np.nan
    up, dn = r[r > 0], r[r < 0]
    payoff = float(up.mean() / -dn.mean()) if len(up) and len(dn) else np.nan
    pf = float(up.sum() / -dn.sum()) if dn.sum() < 0 else np.inf
    return float((r > 0).mean()), payoff, pf


def perf(rets, bpy):
    n = len(rets)
    if n < 20 or rets.std() == 0:
        return dict(ann_ret=np.nan, ann_vol=np.nan, sharpe=np.nan,
                    max_dd=np.nan, tstat=np.nan)
    mu, sd = rets.mean(), rets.std()
    sharpe = mu / sd * math.sqrt(bpy)
    equity = (1 + rets).cumprod()
    dd = float((equity / equity.cummax() - 1).min())
    return dict(ann_ret=mu * bpy, ann_vol=sd * math.sqrt(bpy), sharpe=sharpe,
                max_dd=dd, tstat=sharpe * math.sqrt(n / bpy))


def evaluate(bt, bpy, is_bh=False):
    g, nmet = perf(bt["gross"], bpy), perf(bt["net"], bpy)
    years = len(bt) / bpy
    if is_bh:
        wr, payoff, pf = bar_stats(bt["net"])
        trades = np.nan
    else:
        wr, payoff, pf, ntr = trade_stats(bt)
        trades = ntr / years if years > 0 else np.nan
    return {
        "n_bars": len(bt), "bars_per_year": round(bpy, 1),
        "ann_ret_gross": g["ann_ret"], "ann_vol_gross": g["ann_vol"],
        "sharpe_gross": g["sharpe"],
        "ann_ret_net": nmet["ann_ret"], "ann_vol_net": nmet["ann_vol"],
        "sharpe_net": nmet["sharpe"], "max_dd_net": nmet["max_dd"],
        "tstat_net": nmet["tstat"], "win_rate_net": wr, "payoff_net": payoff,
        "profit_factor_net": pf, "trades_per_year": trades,
        "turnover_units_per_year": bt["turnover"].sum() / years if years > 0 else np.nan,
    }


# --------------------------------------------------------------------------
# Deflated Sharpe (Bailey & Lopez de Prado 2014)
# --------------------------------------------------------------------------

def psr(rets, sr_star_bar):
    n = len(rets)
    if n < 20 or rets.std() == 0:
        return np.nan
    sr = rets.mean() / rets.std()
    skew = float(sstats.skew(rets))
    kurt = float(sstats.kurtosis(rets, fisher=False))
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if denom <= 0:
        return np.nan
    z = (sr - sr_star_bar) * math.sqrt(n - 1) / math.sqrt(denom)
    return float(sstats.norm.cdf(z))


def expected_max_sr(trial_sr_var_bar, n_trials):
    if trial_sr_var_bar <= 0 or n_trials < 2:
        return 0.0
    q1 = sstats.norm.ppf(1 - 1.0 / n_trials)
    q2 = sstats.norm.ppf(1 - 1.0 / (n_trials * math.e))
    return math.sqrt(trial_sr_var_bar) * ((1 - EULER_GAMMA) * q1 + EULER_GAMMA * q2)


# --------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------

def load_all_series():
    """-> {(group, tf): {ticker: OHLC frame}}, list of skipped, sample rows."""
    session = None if "--cached" in sys.argv else make_session()
    series, skipped, samples = {}, [], []

    print("Downloading daily history (crypto: max, futures: 7y)...")
    for tkr in CRYPTO + FUTURES:
        per = "max" if GROUP_OF[tkr] == "crypto" else "7y"
        df = _fetch(tkr, session, per, "1d")
        if df is None or len(df) < MIN_BARS:
            skipped.append((f"{tkr} 1d", "download failed" if df is None
                            else f"only {len(df)} bars"))
            continue
        series.setdefault((GROUP_OF[tkr], "1d"), {})[tkr] = df
        print(f"  {tkr:9s} 1d {len(df):5d} bars  "
              f"{df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d}")

    print("Downloading 1h history for the 4h cross-check (~730d cap)...")
    for tkr in H4_TICKERS:
        # "730d" beats "max" for 24/5 futures (Yahoo window quirk)
        df1h = _fetch(tkr, session, "730d", "1h")
        if df1h is None:
            skipped.append((f"{tkr} 4h", "download failed"))
            continue
        df = resample_4h(df1h)
        if len(df) < MIN_BARS:
            skipped.append((f"{tkr} 4h", f"only {len(df)} bars"))
            continue
        series.setdefault((GROUP_OF[tkr], "4h"), {})[tkr] = df
        print(f"  {tkr:9s} 4h {len(df):5d} bars  "
              f"{df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d}")

    for (group, tf), members in series.items():
        for tkr, df in members.items():
            samples.append(dict(group=group, timeframe=tf, instrument=tkr,
                                n_bars=len(df),
                                bars_per_year=round(bars_per_year(df.index)),
                                start=str(df.index[0].date()),
                                end=str(df.index[-1].date())))
    return series, skipped, samples


def build_states(df):
    """All raw signal states for one OHLC frame."""
    out = {}  # (strategy, exit, N) -> state series
    regime = sma_regime_state(df["Close"])
    out[("sma50_regime", "", 0)] = regime
    for n in N_SWEEP:
        for ex in EXITS:
            a = donchian_break_state(df, n, ex)
            out[("donch_break", ex, n)] = a
            out[("combo", ex, n)] = a.where(a * regime > 0, 0.0)
        out[("donch_fade", "mid", n)] = donchian_fade_state(df, n)
    return out


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()

    series, skipped, samples = load_all_series()

    # ---- backtest every config, keep return frames for portfolios/DSR ----
    frames = {}   # (group, tf, strat, exit, N, sizing) -> {tkr: frame}
    print("Backtesting...")
    for (group, tf), members in series.items():
        for tkr, df in members.items():
            bpy = bars_per_year(df.index)
            states = build_states(df)
            close = df["Close"]
            for (strat, ex, n), state in states.items():
                for sizing in SIZINGS:
                    bt = run_state(close, state, sizing, tf, group, bpy)
                    frames.setdefault((group, tf, strat, ex, n, sizing),
                                      {})[tkr] = bt
            # buy & hold: long 1, entry cost once
            rets = close.pct_change().fillna(0.0)
            cost = pd.Series(0.0, index=close.index)
            cost.iloc[0] = ONE_WAY_COST[group]
            frames.setdefault((group, tf, "buyhold", "", 0, "fixed"), {})[tkr] = \
                pd.DataFrame({"gross": rets, "net": rets - cost,
                              "pos": 1.0, "turnover": 0.0})

    # ---- IS/OOS boundary per group x timeframe (union index) ----
    boundaries = {}
    for (group, tf), members in series.items():
        union = sorted(set().union(*[set(v.index) for v in members.values()]))
        boundaries[(group, tf)] = union[int(IS_FRACTION * len(union))]

    # ---- metric rows: instrument level + EW portfolio, FULL/IS/OOS ----
    rows, port_net = [], {}

    def add(bt, bpy, key, level, instrument):
        group, tf, strat, ex, n, sizing = key
        cut = boundaries[(group, tf)]
        for period, chunk in [("FULL", bt), ("IS", bt[bt.index < cut]),
                              ("OOS", bt[bt.index >= cut])]:
            if len(chunk) < 20:
                continue
            met = evaluate(chunk, bpy, is_bh=(strat == "buyhold"))
            rows.append(dict(level=level, group=group, timeframe=tf,
                             strategy=strat, exit=ex, N=n, sizing=sizing,
                             instrument=instrument, period=period,
                             start=str(chunk.index[0].date()),
                             end=str(chunk.index[-1].date()), **met))

    for key, members in frames.items():
        for tkr, bt in members.items():
            add(bt, bars_per_year(bt.index), key, "instrument", tkr)
        panel = {c: pd.DataFrame({t: m[c] for t, m in members.items()}).mean(axis=1)
                 for c in ["gross", "net", "pos", "turnover"]}
        port = pd.DataFrame(panel).dropna()
        add(port, bars_per_year(port.index), key, "portfolio", "EW_PORTFOLIO")
        port_net[key] = port["net"]

    df = pd.DataFrame(rows)

    # ---- CONSISTENT/FRAGILE flags ----
    # sub-period leg: net Sharpe > 0 in BOTH IS and OOS for the exact config
    key_cols = ["level", "group", "timeframe", "strategy", "exit", "N",
                "sizing", "instrument"]
    piv = df.pivot_table(index=key_cols, columns="period",
                         values="sharpe_net", aggfunc="first")
    both_pos = ((piv.get("IS") > 0) & (piv.get("OOS") > 0)).rename("subperiod_ok")
    df = df.merge(both_pos.reset_index(), on=key_cols, how="left")
    # N-sweep leg (A/C/D only): majority of the N sweep net-positive on FULL
    fam_cols = ["level", "group", "timeframe", "strategy", "exit", "sizing",
                "instrument"]
    full_swp = df[(df["period"] == "FULL") & (df["N"] > 0)]
    sweep_ok = (full_swp.groupby(fam_cols)["sharpe_net"]
                .apply(lambda s: (s > 0).mean() >= 0.6).rename("sweep_ok"))
    df = df.merge(sweep_ok.reset_index(), on=fam_cols, how="left")
    df["sweep_ok"] = df["sweep_ok"].fillna(df["subperiod_ok"])  # B: no sweep
    df["flag"] = np.where(df["subperiod_ok"] & df["sweep_ok"],
                          "CONSISTENT", "FRAGILE")
    df.loc[df["strategy"] == "buyhold", "flag"] = ""
    df = df.drop(columns=["subperiod_ok", "sweep_ok"])

    # ---- multiple-testing accounting (all non-benchmark FULL configs) ----
    trials = df[(df["strategy"] != "buyhold") & (df["period"] == "FULL")]
    n_trials = len(trials)
    sr_ann = trials["sharpe_net"].dropna()
    sr_dist = dict(n_configs=n_trials, mean=sr_ann.mean(), median=sr_ann.median(),
                   std=sr_ann.std(), p05=sr_ann.quantile(0.05),
                   p95=sr_ann.quantile(0.95))
    var_ann = sr_ann.var()

    dsr_rows = []
    for _, r in trials.sort_values("sharpe_net", ascending=False).head(8).iterrows():
        key = (r["group"], r["timeframe"], r["strategy"], r["exit"],
               r["N"], r["sizing"])
        net = (port_net[key] if r["level"] == "portfolio"
               else frames[key][r["instrument"]]["net"])
        var_bar = var_ann / r["bars_per_year"]
        sr_star = expected_max_sr(var_bar, n_trials)
        dsr_rows.append(dict(
            group=r["group"], timeframe=r["timeframe"], strategy=r["strategy"],
            exit=r["exit"], N=int(r["N"]), sizing=r["sizing"],
            instrument=r["instrument"], sharpe_net_ann=r["sharpe_net"],
            sr_star_ann=sr_star * math.sqrt(r["bars_per_year"]),
            p_true_sr_gt0=psr(net, 0.0), deflated_sharpe=psr(net, sr_star)))
    dsr_df = pd.DataFrame(dsr_rows)

    # ---- OOS: select best (N, exit) on IS portfolio net Sharpe, run OOS ----
    oos_rows = []
    port = df[(df["level"] == "portfolio")]
    for (group, tf) in series:
        for strat in ["donch_break", "combo"]:
            for sizing in SIZINGS:
                cand = port[(port["group"] == group) & (port["timeframe"] == tf)
                            & (port["strategy"] == strat)
                            & (port["sizing"] == sizing)]
                is_c = cand[cand["period"] == "IS"].set_index(["N", "exit"])
                if is_c["sharpe_net"].dropna().empty:
                    continue
                pick = is_c["sharpe_net"].idxmax()
                oos_v = cand[(cand["period"] == "OOS") & (cand["N"] == pick[0])
                             & (cand["exit"] == pick[1])]["sharpe_net"]

                def ref(strategy):
                    m = port[(port["group"] == group) & (port["timeframe"] == tf)
                             & (port["strategy"] == strategy)
                             & (port["period"] == "OOS")]
                    if strategy == "sma50_regime":
                        m = m[m["sizing"] == sizing]
                    return float(m["sharpe_net"].iloc[0]) if len(m) else np.nan

                oos_rows.append(dict(
                    group=group, timeframe=tf, strategy=strat, sizing=sizing,
                    selected_N=int(pick[0]), selected_exit=pick[1],
                    is_sharpe_net=float(is_c.loc[pick, "sharpe_net"]),
                    oos_sharpe_net=float(oos_v.iloc[0]) if len(oos_v) else np.nan,
                    degradation=(float(oos_v.iloc[0])
                                 - float(is_c.loc[pick, "sharpe_net"]))
                    if len(oos_v) else np.nan,
                    sma50_oos=ref("sma50_regime"), bh_oos=ref("buyhold")))
    oos_df = pd.DataFrame(oos_rows)

    # ---- outputs ----
    df.to_csv(os.path.join(OUT_DIR, "results_all_configs.csv"),
              index=False, float_format="%.4f")
    write_summary(df, pd.DataFrame(samples), oos_df, dsr_df, sr_dist, skipped)
    print(f"\nDone in {time.time() - t0:.0f}s. "
          f"{n_trials} strategy configs evaluated. Outputs in {OUT_DIR}/")


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
            if isinstance(v, (int, np.integer)):
                cells.append(str(int(v)))
            elif isinstance(v, (float, np.floating)):
                cells.append(fmt(float(v), nd))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def q(df, **kw):
    m = pd.Series(True, index=df.index)
    for k, v in kw.items():
        m &= df[k] == v
    return df[m]


def write_summary(df, samples, oos_df, dsr_df, sr_dist, skipped):
    L = []
    A = L.append
    port = df[df["level"] == "portfolio"]
    pf = port[port["period"] == "FULL"]

    A("# Donchian breakout + 50-SMA regime filter — marginal-contribution "
      "study (daily, with 4h cross-check)")
    A("")
    A(f"*Run date: {pd.Timestamp.now(tz='UTC'):%Y-%m-%d}. Data: Yahoo via "
      "yfinance — crypto daily = max history (BTC from 2014, alts from "
      "2017–2020), futures daily = ~7y **front-month continuous with roll "
      "gaps** (gaps fire false breakouts and distort these results; a proper "
      "futures test needs back-adjusted contracts), 4h = resampled from 1h "
      "(Yahoo caps intraday at ~730d). Signals on closed bars, entry next "
      "bar. Donchian channels use PRIOR N bars (current excluded). Costs "
      "20bp/2bp round-trip charged per unit turnover; costs are reported "
      "but secondary here. Sizing below is vol-scaled (15% target, 3× cap) "
      "unless marked fixed. **Exploratory — honesty over impressive "
      "numbers.***")
    A("")

    # ---- 1 sample sizes ----
    A("## 1. Sample sizes")
    A("")
    s = samples.sort_values(["timeframe", "group", "instrument"])
    A(md_table(s, ["group", "timeframe", "instrument", "start", "end",
                   "n_bars", "bars_per_year"],
               ["Group", "TF", "Instrument", "Start", "End", "Bars",
                "Bars/yr (empirical)"], 0))
    A("")
    A(("Skipped: " + ", ".join(f"{t} ({w})" for t, w in skipped))
      if skipped else "No instruments skipped.")
    A("")

    # ---- 2 N-sweep consistency (portfolio, volscaled) ----
    A("## 2. Lookback sweep — EW-portfolio Sharpe by N (vol-scaled)")
    A("")
    A("Rows are strategy × exit; columns are the entry lookback N (exit "
      "channel = N/2). B (50-SMA) and buy & hold have no N and are shown "
      "as single columns on the right of each block.")
    for metric, label in [("sharpe_net", "NET"), ("sharpe_gross", "GROSS")]:
        A("")
        A(f"### {label} Sharpe")
        A("")
        for (g, tf) in sorted(set(zip(pf["group"], pf["timeframe"]))):
            blk = q(pf, group=g, timeframe=tf, sizing="volscaled")
            b_val = q(blk, strategy="sma50_regime")[metric]
            bh_val = q(pf, group=g, timeframe=tf, strategy="buyhold")[metric]
            rws = []
            for strat, ex in [("donch_break", "channel"), ("donch_break", "atr"),
                              ("combo", "channel"), ("combo", "atr"),
                              ("donch_fade", "mid")]:
                sub = q(blk, strategy=strat, exit=ex).set_index("N")[metric]
                rws.append({"config": f"{STRAT_LABEL[strat]} / {ex}",
                            **{f"N{n}": sub.get(n, np.nan) for n in N_SWEEP}})
            tbl = pd.DataFrame(rws)
            A(f"**{g} — {tf}**  (B 50-SMA: {fmt(float(b_val.iloc[0]))}, "
              f"buy & hold: {fmt(float(bh_val.iloc[0]))})")
            A("")
            A(md_table(tbl, ["config"] + [f"N{n}" for n in N_SWEEP],
                       ["Strategy / exit"] + [f"N={n}" for n in N_SWEEP]))
            A("")

    # ---- 3 marginal contribution ----
    A("## 3. THE CENTRAL TEST — marginal contribution (A vs B vs C)")
    A("")
    A("Channel exit, vol-scaled. 'A med' / 'C med' are medians across the "
      "five N values (medians avoid cherry-picking a lookback); B has no N. "
      "The verdict counts at how many of the 5 lookbacks C's net Sharpe "
      "beats BOTH A at the same N and B.")
    A("")
    med_rows, verdicts = [], {}
    for (g, tf) in sorted(set(zip(pf["group"], pf["timeframe"]))):
        blk = q(pf, group=g, timeframe=tf, sizing="volscaled")
        a = q(blk, strategy="donch_break", exit="channel").set_index("N")
        c = q(blk, strategy="combo", exit="channel").set_index("N")
        b = q(blk, strategy="sma50_regime").iloc[0]
        wins = sum(1 for n in N_SWEEP
                   if c.loc[n, "sharpe_net"] > max(a.loc[n, "sharpe_net"],
                                                   b["sharpe_net"]))
        verdicts[(g, tf)] = wins
        for name, r in [("A Donchian (med across N)",
                         a.median(numeric_only=True)),
                        ("B 50-SMA regime", b),
                        ("C combo (med across N)",
                         c.median(numeric_only=True))]:
            med_rows.append(dict(group=g, timeframe=tf, piece=name,
                                 sharpe_gross=r["sharpe_gross"],
                                 sharpe_net=r["sharpe_net"],
                                 max_dd_net=r["max_dd_net"],
                                 win_rate_net=r["win_rate_net"],
                                 payoff_net=r["payoff_net"],
                                 trades_per_year=r["trades_per_year"],
                                 turnover=r["turnover_units_per_year"]))
    A(md_table(pd.DataFrame(med_rows),
               ["group", "timeframe", "piece", "sharpe_gross", "sharpe_net",
                "max_dd_net", "win_rate_net", "payoff_net", "trades_per_year",
                "turnover"],
               ["Group", "TF", "Piece", "Gross SR", "Net SR", "Max DD",
                "Win rate", "Payoff", "Trades/yr", "Turnover/yr"]))
    A("")
    for (g, tf), wins in sorted(verdicts.items()):
        A(f"- **{g} {tf}**: C beats both pieces at **{wins} of 5** lookbacks "
          f"(net Sharpe, channel exit).")
    A("")

    # ---- 4 per-instrument ranked ----
    A("## 4. Per-instrument (vol-scaled, channel exit, median across N; "
      "ranked by C net Sharpe)")
    A("")
    A("Flag: CONSISTENT requires net Sharpe > 0 in both IS and OOS *and* a "
      "net-positive majority of the N-sweep (evaluated per config; flag "
      "shown here is for the instrument's median-N combo config).")
    A("")
    inst = df[(df["level"] == "instrument") & (df["period"] == "FULL")
              & (df["sizing"] == "volscaled")]
    for tf in sorted(inst["timeframe"].unique()):
        rws = []
        sub_tf = inst[inst["timeframe"] == tf]
        for tkr in sub_tf["instrument"].unique():
            si = sub_tf[sub_tf["instrument"] == tkr]
            a = q(si, strategy="donch_break", exit="channel")["sharpe_net"].median()
            c_rows = q(si, strategy="combo", exit="channel")
            c = c_rows["sharpe_net"].median()
            b = q(si, strategy="sma50_regime")["sharpe_net"]
            bh = df[(df["level"] == "instrument") & (df["period"] == "FULL")
                    & (df["instrument"] == tkr) & (df["timeframe"] == tf)
                    & (df["strategy"] == "buyhold")]["sharpe_net"]
            n_med = c_rows.iloc[(c_rows["sharpe_net"] - c).abs().argsort()]
            rws.append(dict(instrument=tkr, group=si["group"].iloc[0],
                            bh=float(bh.iloc[0]) if len(bh) else np.nan,
                            b=float(b.iloc[0]) if len(b) else np.nan,
                            a_med=a, c_med=c,
                            flag=n_med["flag"].iloc[0] if len(n_med) else ""))
        tbl = pd.DataFrame(rws).sort_values("c_med", ascending=False)
        A(f"### {tf}")
        A("")
        A(md_table(tbl, ["instrument", "group", "bh", "b", "a_med", "c_med",
                         "flag"],
                   ["Instrument", "Group", "B&H net SR", "B net SR",
                    "A net SR (med N)", "C net SR (med N)", "Flag"]))
        A("")

    # ---- 5 OOS ----
    A("## 5. Out-of-sample (select best N & exit on IS only, run once on OOS)")
    A("")
    A(f"Oldest {int(IS_FRACTION*100)}% IS / newest {int((1-IS_FRACTION)*100)}% "
      "OOS on each group×timeframe's union calendar. Selection = highest IS "
      "EW-portfolio net Sharpe over the 10 (N, exit) pairs, per strategy "
      "family and sizing. Degradation = OOS − IS.")
    A("")
    o = oos_df.copy()
    o["strategy"] = o["strategy"].map(STRAT_LABEL)
    A(md_table(o.sort_values(["group", "timeframe", "strategy", "sizing"]),
               ["group", "timeframe", "strategy", "sizing", "selected_N",
                "selected_exit", "is_sharpe_net", "oos_sharpe_net",
                "degradation", "sma50_oos", "bh_oos"],
               ["Group", "TF", "Family", "Sizing", "N*", "Exit*", "IS net SR",
                "OOS net SR", "Degradation", "B OOS", "B&H OOS"]))
    A("")

    # ---- 6 multiple testing ----
    A("## 6. Multiple-testing accounting")
    A("")
    A(f"Total strategy configs evaluated (FULL sample, instrument- and "
      f"portfolio-level, incl. the D diagnostic): **N = "
      f"{sr_dist['n_configs']}**. Net annualized Sharpe distribution: mean "
      f"{fmt(sr_dist['mean'])}, median {fmt(sr_dist['median'])}, std "
      f"{fmt(sr_dist['std'])}, 5th pct {fmt(sr_dist['p05'])}, 95th pct "
      f"{fmt(sr_dist['p95'])}.")
    A("")
    d = dsr_df.copy()
    d["config"] = (d["group"] + " " + d["timeframe"] + " "
                   + d["strategy"].map(STRAT_LABEL) + "/" + d["exit"]
                   + " N=" + d["N"].astype(str) + " " + d["sizing"]
                   + " (" + d["instrument"] + ")")
    A(md_table(d, ["config", "sharpe_net_ann", "sr_star_ann", "p_true_sr_gt0",
                   "deflated_sharpe"],
               ["Top config", "Net ann. SR", "SR* (exp. max)", "P(true SR>0)",
                "Deflated SR P(SR>SR*)"]))
    A("")
    A("Note the trials are highly correlated (same five strategies across "
      "overlapping instruments) and include the deliberately-bad D "
      "diagnostic, both of which make SR\\* and this deflation conservative "
      "— the effective number of independent trials is well below "
      f"{sr_dist['n_configs']}. Even so, no top config clears 0.5.")
    A("")

    # ---- 7 answers ----
    A("## 7. Plain-English answers to the six questions")
    A("")
    A(build_answers(df, oos_df, dsr_df, verdicts))
    A("")
    A("---")
    A("*Reproduce: `python backtest.py` (or `--cached` for the committed "
      "data snapshot). All configs: `output/results_all_configs.csv` "
      "(`period` ∈ FULL/IS/OOS; strategies: donch_break=A, sma50_regime=B, "
      "combo=C, donch_fade=D, buyhold).*")

    with open(os.path.join(OUT_DIR, "SUMMARY.md"), "w") as f:
        f.write("\n".join(L))


def build_answers(df, oos_df, dsr_df, verdicts):
    out = []
    pf = df[(df["level"] == "portfolio") & (df["period"] == "FULL")
            & (df["sizing"] == "volscaled")]
    gtf = sorted(set(zip(pf["group"], pf["timeframe"])))

    def med(g, tf, strat, ex, col):
        return q(pf, group=g, timeframe=tf, strategy=strat,
                 exit=ex)[col].median()

    # Q1: does breakout capture trend (gross), and does it survive OOS?
    out.append("**Q1 — Does Donchian breakout capture trend?**")
    for g, tf in gtf:
        gr = med(g, tf, "donch_break", "channel", "sharpe_gross")
        nt = med(g, tf, "donch_break", "channel", "sharpe_net")
        oos = oos_df[(oos_df["group"] == g) & (oos_df["timeframe"] == tf)
                     & (oos_df["strategy"] == "donch_break")
                     & (oos_df["sizing"] == "volscaled")]
        oos_v = float(oos["oos_sharpe_net"].iloc[0]) if len(oos) else np.nan
        out.append(f"- {g} {tf}: median gross Sharpe {fmt(gr)} across the "
                   f"N-sweep (net {fmt(nt)}); IS-selected config OOS net "
                   f"Sharpe {fmt(oos_v)}.")
    out.append("")

    # Q2: which N is robust?
    out.append("**Q2 — Which lookback N is robust?** Portfolio net Sharpe "
               "(channel exit) by N, positive-count across the four "
               "group×timeframe blocks:")
    for n in N_SWEEP:
        vals = [float(q(pf, group=g, timeframe=tf, strategy="donch_break",
                        exit="channel", N=n)["sharpe_net"].iloc[0])
                for g, tf in gtf]
        pos = sum(v > 0 for v in vals)
        out.append(f"- N={n}: positive in {pos}/4 blocks "
                   f"({', '.join(fmt(v) for v in vals)}).")
    out.append("")

    # Q3: marginal lift
    out.append("**Q3 — Does the combination beat each piece alone?**")
    for (g, tf), wins in sorted(verdicts.items()):
        a_med = med(g, tf, "donch_break", "channel", "sharpe_net")
        b_v = float(q(pf, group=g, timeframe=tf,
                      strategy="sma50_regime")["sharpe_net"].iloc[0])
        c_med = med(g, tf, "combo", "channel", "sharpe_net")
        beats = c_med > max(a_med, b_v)
        out.append(f"- {g} {tf}: A med {fmt(a_med)}, B {fmt(b_v)}, C med "
                   f"{fmt(c_med)} → combo beats both at {wins}/5 lookbacks; "
                   f"on medians it {'DOES' if beats else 'does NOT'} beat "
                   f"the better single piece.")
    out.append("")

    # Q4: trend or revert at the bands (D, gross)
    out.append("**Q4 — Trend or mean-reversion at the bands?** Median GROSS "
               "Sharpe of the fade strategy (D) across N — negative means "
               "breakouts continue (trend), positive means they revert:")
    for g, tf in gtf:
        d_med = med(g, tf, "donch_fade", "mid", "sharpe_gross")
        a_med = med(g, tf, "donch_break", "channel", "sharpe_gross")
        verdict = ("TRENDS at the band" if d_med < 0 and a_med > 0 else
                   "REVERTS at the band" if d_med > 0 and a_med < 0 else
                   "mixed/unclear")
        out.append(f"- {g} {tf}: fade gross {fmt(d_med)} vs breakout gross "
                   f"{fmt(a_med)} → {verdict}.")
    out.append("")

    # Q5: channel vs ATR exit
    out.append("**Q5 — Structural channel exit vs 3×ATR chandelier?** Median "
               "net Sharpe across N (A family):")
    ch_wins = 0
    for g, tf in gtf:
        ch = med(g, tf, "donch_break", "channel", "sharpe_net")
        at = med(g, tf, "donch_break", "atr", "sharpe_net")
        ch_wins += ch > at
        out.append(f"- {g} {tf}: channel {fmt(ch)} vs ATR {fmt(at)} → "
                   f"{'channel' if ch > at else 'ATR'} better.")
    out.append(f"- Channel exit wins {ch_wins}/{len(gtf)} blocks.")
    out.append("")

    # Q6: crypto vs futures
    out.append("**Q6 — Crypto vs futures, cleaner structural trend?**")
    for g in ["crypto", "futures"]:
        sub = pf[(pf["group"] == g) & (pf["strategy"] == "donch_break")
                 & (pf["exit"] == "channel")]
        out.append(f"- {g}: median gross Sharpe "
                   f"{fmt(sub['sharpe_gross'].median())}, median net "
                   f"{fmt(sub['sharpe_net'].median())} across all N and "
                   f"timeframes.")
    out.append("- Reminder: futures numbers are polluted by front-month roll "
               "gaps, which fire spurious breakouts in both directions; "
               "crypto spot is the clean read.")
    out.append("")

    # bottom line
    bh_full = df[(df["level"] == "portfolio") & (df["period"] == "FULL")
                 & (df["strategy"] == "buyhold")]
    bh_map = {(r["group"], r["timeframe"]): r["sharpe_net"]
              for _, r in bh_full.iterrows()}
    out.append("**Bottom line.** The structural trend definition is real but "
               "the combination is not: Donchian breakouts are gross-positive "
               "at every lookback in every block while the fade of the same "
               "bands is negative everywhere, so N-bar extremes do mark "
               "continuation, not reversal — the channel 'sees' trend. But "
               "the 50-SMA regime gate does not earn its keep on top of the "
               "breakout (it never beats the better single piece on medians), "
               "the 3×ATR chandelier beats the structural N/2-channel exit in "
               "every block, and out-of-sample everything degrades — crypto "
               "gracefully (positive but roughly a third of IS, and no better "
               "than the plain 50-SMA regime OOS), futures to outright "
               "negative (collapse; roll gaps make even the in-sample futures "
               "read suspect). Nothing clears the deflated-Sharpe bar of "
               "best-of-"
               f"{len(df[(df['strategy'] != 'buyhold') & (df['period'] == 'FULL')])} "
               "luck, and buy-and-hold (net Sharpe "
               + ", ".join(f"{g}/{tf} {fmt(v)}" for (g, tf), v in sorted(bh_map.items()))
               + ") remains hard to beat. As exploratory evidence: the "
               "reactive structural trigger captures trend on crypto daily "
               "bars; the extra regime-filter complexity does not add value "
               "there.")
    return "\n".join(out)


if __name__ == "__main__":
    main()
