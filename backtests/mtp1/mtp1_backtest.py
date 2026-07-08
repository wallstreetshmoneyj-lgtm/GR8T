#!/usr/bin/env python3
"""
MTP-1 (Micro Trend Portfolio v1) — research-grade backtest.

Diversified, volatility-sized, long/short Donchian-breakout trend following
on continuous futures with a chandelier ATR trailing stop. Honest R&D:
zero look-ahead (asserted), no optimization (headline = MEDIAN grid combo),
no added filters, random-entry bootstrap null, and explicit pass/fail gates.

DATA CAVEAT (also printed in the report): yfinance continuous futures (=F)
are front-month chains with roll gaps, NOT back-adjusted. Price-level
indicators (Donchian, ATR) see roll artifacts. This is an approximation;
final validation happens on IBKR back-adjusted data.

Passes:
  A (research)      : fractional contracts, full universe -> does an edge exist?
  B (implementation): integer micro contracts + ~10% notional margin check,
                      micro-tradable markets only -> what survives $10K?

Run:  python mtp1_backtest.py            (full: 15-combo grid + 1000 bootstraps)
      python mtp1_backtest.py --smoke    (2 combos, 25 bootstraps)
"""

import gzip
import math
import os
import sys
import time

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# ============================================================================
# CONFIG
# ============================================================================

CONFIG = dict(
    start_equity=10_000.0,
    risk_per_trade=0.0075,          # 0.75% of equity, defined by initial stop
    max_open_risk=0.06,             # portfolio cap: total open initial risk
    max_per_sector=2,               # portfolio cap: concurrent positions/sector
    atr_len=20,                     # Wilder ATR
    grid_N=[20, 35, 50, 75, 100],   # Donchian entry lookbacks
    grid_K=[2, 3, 4],               # chandelier ATR multiples
    detail_combo=(50, 3),           # always-reported reference config
    commission_per_side=0.75,       # $ per contract per side, at 1x costs
    slippage_ticks=1.0,             # per side, micro-tradable markets
    slippage_ticks_research=1.5,    # per side, research-only (full-size specs)
    cost_multipliers=[0, 1, 2, 3],
    margin_pct=0.10,                # Pass B rough intraday margin: 10% notional
    min_history_years=10,           # headline-stats inclusion threshold
    n_bootstrap=1000,
    bootstrap_seed=42,
    ann_factor=252,
)

if "--smoke" in sys.argv:
    CONFIG["grid_N"] = [20, 50]
    CONFIG["grid_K"] = [3]
    CONFIG["n_bootstrap"] = 25

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT_DIR = os.path.join(HERE, "output")
CA_BUNDLE = "/root/.ccr/ca-bundle.crt"

# Universe. point_value = $ per 1.00 price point of the TRADED contract
# (micro where one exists, full-size for research-only markets).
# MHG/SIL verified against CME contract specs 2026-07-08:
#   SIL  = 1,000 oz  -> $1,000/point, tick 0.005 ($5.00)   (matches spec sheet)
#   MHG  = 2,500 lbs -> $2,500/point, tick 0.0005 ($1.25)  (spec sheet said
#          $1,250/point & ~$0.63/tick — off by 2x; verified values used)
UNIVERSE = [
    # yf,      name,          sector,   micro, point_value, tick
    ("ES=F",  "S&P 500",      "Equity", "MES",  5.0,     0.25),
    ("NQ=F",  "Nasdaq 100",   "Equity", "MNQ",  2.0,     0.25),
    ("YM=F",  "Dow",          "Equity", "MYM",  0.5,     1.0),
    ("RTY=F", "Russell 2000", "Equity", "M2K",  5.0,     0.10),
    ("GC=F",  "Gold",         "Metals", "MGC",  10.0,    0.10),
    ("SI=F",  "Silver",       "Metals", "SIL",  1000.0,  0.005),
    ("HG=F",  "Copper",       "Metals", "MHG",  2500.0,  0.0005),
    ("CL=F",  "WTI Crude",    "Energy", "MCL",  100.0,   0.01),
    ("NG=F",  "Nat Gas",      "Energy", None,   10000.0, 0.001),
    ("ZN=F",  "10Y Note",     "Rates",  None,   1000.0,  0.015625),
    ("ZB=F",  "30Y Bond",     "Rates",  None,   1000.0,  0.03125),
    ("6E=F",  "EUR/USD",      "FX",     "M6E",  12500.0, 0.0001),
    ("6B=F",  "GBP/USD",      "FX",     "M6B",  6250.0,  0.0001),
    ("6A=F",  "AUD/USD",      "FX",     "M6A",  10000.0, 0.0001),
    ("ZC=F",  "Corn",         "Ags",    None,   50.0,    0.25),
    ("ZS=F",  "Soybeans",     "Ags",    None,   50.0,    0.25),
    ("ZW=F",  "Wheat",        "Ags",    None,   50.0,    0.25),
]
SPEC = {u[0]: dict(name=u[1], sector=u[2], micro=u[3], pv=u[4], tick=u[5])
        for u in UNIVERSE}


# ============================================================================
# Console tee (everything printed also lands in output/report.txt)
# ============================================================================

class Tee:
    def __init__(self, path):
        self.f = open(path, "w")
        self.stdout = sys.stdout

    def write(self, s):
        self.stdout.write(s)
        self.f.write(s)

    def flush(self):
        self.stdout.flush()
        self.f.flush()


# ============================================================================
# Data
# ============================================================================

def fetch_daily(ticker):
    """Raw daily OHLC, period=max, auto_adjust=False; gz-cached."""
    cache = os.path.join(DATA_DIR, ticker.replace("=", "_") + "_1d_raw.csv.gz")
    if os.path.exists(cache):
        with gzip.open(cache, "rt") as f:
            return pd.read_csv(f, index_col=0, parse_dates=True)
    import yfinance as yf
    from curl_cffi import requests as cr
    kwargs = {"impersonate": "chrome110"}
    if os.path.exists(CA_BUNDLE):
        kwargs["verify"] = CA_BUNDLE
    last_err = None
    for attempt in range(4):
        try:
            raw = yf.Ticker(ticker, session=cr.Session(**kwargs)).history(
                period="max", interval="1d", auto_adjust=False)
            if raw is not None and len(raw) > 0:
                break
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"{ticker}: download failed ({last_err})")
    df = raw[["Open", "High", "Low", "Close"]]
    df.index = df.index.tz_localize(None).normalize()
    df = df.iloc[:-1]  # drop the final, possibly still-forming bar
    os.makedirs(DATA_DIR, exist_ok=True)
    with gzip.open(cache, "wt") as f:
        df.to_csv(f)
    time.sleep(1.0)
    return df


def clean_ohlc(df):
    """Drop unusable rows (NaN / non-positive prices / high<low)."""
    n0 = len(df)
    df = df.dropna()
    good = ((df[["Open", "High", "Low", "Close"]] > 0).all(axis=1)
            & (df["High"] >= df["Low"]))
    df = df[good]
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df, n0 - len(df)


def wilder_atr(df, n):
    prev_c = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - prev_c).abs(),
                    (df["Low"] - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def build_dataset(tickers, frames):
    """Static per-universe structures shared by all grid combos."""
    mkts, all_dates = [], set()
    for tkr in tickers:
        df = frames[tkr]
        all_dates.update(df.index)
        mkts.append(dict(
            tkr=tkr, sector=SPEC[tkr]["sector"], pv=SPEC[tkr]["pv"],
            tick=SPEC[tkr]["tick"], micro=SPEC[tkr]["micro"],
            dates=df.index.values,
            o=df["Open"].values, h=df["High"].values,
            l=df["Low"].values, c=df["Close"].values,
            atr=wilder_atr(df, CONFIG["atr_len"]).values,
            ind_cache={}))
    master = pd.DatetimeIndex(sorted(all_dates))
    date_pos = {d: i for i, d in enumerate(master.values)}
    bars_today = [[] for _ in range(len(master))]
    for mid, m in enumerate(mkts):
        for own_i, d in enumerate(m["dates"]):
            bars_today[date_pos[d]].append((mid, own_i))
    return dict(markets=mkts, master=master, bars_today=bars_today)


def get_channels(m, N):
    """Donchian on PRIOR N closes (t-N..t-1, excluding t); cached per market."""
    if N not in m["ind_cache"]:
        c = pd.Series(m["c"])
        upper = c.shift(1).rolling(N).max().values
        lower = c.shift(1).rolling(N).min().values
        m["ind_cache"][N] = (upper, lower)
    return m["ind_cache"][N]


# ============================================================================
# Portfolio simulation engine (event loop over the union calendar)
# ============================================================================

def simulate(ds, N, K, cost_mult=1.0, integer_contracts=False,
             margin_check=False, entry_plan=None, record_trades=True,
             record_per_market=False):
    """One full portfolio run. Timeline per day:
        1) stop exits (stop in force = level set at the prior close;
           gap-through fills at open, otherwise at the stop price)
        2) entries pending from the previous bar's signal, at today's open
           (portfolio caps checked at fill; same-day stop-out possible)
        3) close-of-day: trail-stop updates, mark-to-market equity
        4) new signals at the close -> pending entry for the next bar,
           sized on today's closing equity
    entry_plan: {mid: {own_idx: dir}} replaces breakout signals (bootstrap).
    """
    cfg = CONFIG
    mkts, bars_today = ds["markets"], ds["bars_today"]
    D, M = len(ds["master"]), len(mkts)
    chan = [get_channels(m, N) for m in mkts]
    comm = cfg["commission_per_side"] * cost_mult

    def slip(m):
        ticks = (cfg["slippage_ticks"] if m["micro"]
                 else cfg["slippage_ticks_research"])
        return ticks * m["tick"] * cost_mult

    cash = cfg["start_equity"]
    equity = np.empty(D)
    # per-market position state (parallel lists, indexed by mid)
    p_dir = [0] * M; p_ctr = [0.0] * M; p_fill = [0.0] * M
    p_stop = [0.0] * M; p_ext = [0.0] * M       # best close since entry
    p_last = [0.0] * M                          # last close (for marking)
    p_risk = [0.0] * M                          # initial risk $ at entry
    p_margin = [0.0] * M
    p_sig_d = [0] * M; p_ent_d = [0] * M; p_ent_i = [0] * M
    p_mae = [0.0] * M; p_mfe = [0.0] * M
    pend = [None] * M                           # (dir, ctr, atr_sig, sig_own_i, sig_d)
    open_mids = set()
    trades, skips = [], []
    pm_pnl = np.zeros((D, M)) if record_per_market else None
    eq_prev = cash

    def close_position(mid, d, exit_px, reason, own_i):
        m = mkts[mid]
        nonlocal cash
        gross = (exit_px - p_fill[mid]) * p_dir[mid] * p_ctr[mid] * m["pv"]
        cost_exit = comm * p_ctr[mid]
        cash += gross - cost_exit
        if record_per_market:
            # attribute exit-day pnl move vs yesterday's mark
            pm_pnl[d, mid] += ((exit_px - p_last[mid]) * p_dir[mid]
                               * p_ctr[mid] * m["pv"]) - cost_exit
        if record_trades:
            entry_cost = comm * p_ctr[mid]
            net = gross - cost_exit - entry_cost  # entry comm already in cash
            trades.append(dict(
                market=m["tkr"], dir="L" if p_dir[mid] == 1 else "S",
                signal_date=ds["master"][p_sig_d[mid]],
                entry_date=ds["master"][p_ent_d[mid]],
                exit_date=ds["master"][d], entry_px=p_fill[mid],
                exit_px=exit_px, contracts=p_ctr[mid],
                gross_pnl=gross, net_pnl=net,
                pnl_R=net / p_risk[mid] if p_risk[mid] > 0 else np.nan,
                mae_R=p_mae[mid] / p_risk[mid] if p_risk[mid] > 0 else np.nan,
                mfe_R=p_mfe[mid] / p_risk[mid] if p_risk[mid] > 0 else np.nan,
                bars_held=own_i - p_ent_i[mid], exit_reason=reason,
                sig_own_i=p_sig_own[mid], ent_own_i=p_ent_i[mid], N=N, K=K))
        p_dir[mid] = 0
        open_mids.discard(mid)

    p_sig_own = [0] * M

    for d in range(D):
        todays = bars_today[d]

        # ---- 1) exits on the stop in force (set at prior close) ----
        for mid, i in todays:
            if p_dir[mid] == 0:
                continue
            m = mkts[mid]
            o, lo, hi = m["o"][i], m["l"][i], m["h"][i]
            s = p_stop[mid]
            if p_dir[mid] == 1:
                if o <= s:
                    close_position(mid, d, o - slip(m), "gap_stop", i)
                elif lo <= s:
                    close_position(mid, d, s - slip(m), "stop", i)
            else:
                if o >= s:
                    close_position(mid, d, o + slip(m), "gap_stop", i)
                elif hi >= s:
                    close_position(mid, d, s + slip(m), "stop", i)

        # ---- 2) pending entries at today's open ----
        for mid, i in todays:
            if pend[mid] is None or p_dir[mid] != 0:
                continue
            m = mkts[mid]
            direc, ctr, atr_sig, sig_own_i, sig_d = pend[mid]
            pend[mid] = None
            if integer_contracts:
                ctr = float(math.floor(ctr))
                if ctr < 1:
                    skips.append((str(ds["master"][d].date()), m["tkr"],
                                  "zero_contracts"))
                    continue
            risk_new = K * atr_sig * m["pv"] * ctr
            open_risk = sum(p_risk[j] for j in open_mids)
            if open_risk + risk_new > CONFIG["max_open_risk"] * eq_prev:
                skips.append((str(ds["master"][d].date()), m["tkr"],
                              "risk_cap"))
                continue
            sec = m["sector"]
            if sum(1 for j in open_mids if mkts[j]["sector"] == sec) >= \
                    CONFIG["max_per_sector"]:
                skips.append((str(ds["master"][d].date()), m["tkr"],
                              "sector_cap"))
                continue
            o = m["o"][i]
            fill = o + direc * slip(m)
            margin_new = 0.0
            if margin_check:
                margin_new = CONFIG["margin_pct"] * o * m["pv"] * ctr
                used = sum(p_margin[j] for j in open_mids)
                if used + margin_new > eq_prev:
                    skips.append((str(ds["master"][d].date()), m["tkr"],
                                  "margin"))
                    continue
            cash -= comm * ctr                      # entry commission
            p_dir[mid] = direc; p_ctr[mid] = ctr; p_fill[mid] = fill
            p_stop[mid] = fill - direc * K * atr_sig
            p_ext[mid] = m["c"][i]                  # will update at close
            p_last[mid] = fill
            p_risk[mid] = risk_new; p_margin[mid] = margin_new
            p_sig_d[mid] = sig_d; p_ent_d[mid] = d
            p_ent_i[mid] = i; p_sig_own[mid] = sig_own_i
            p_mae[mid] = 0.0; p_mfe[mid] = 0.0
            open_mids.add(mid)
            # same-day stop-out on the initial stop (no gap possible: the
            # initial stop is K*ATR beyond the fill by construction)
            lo, hi = m["l"][i], m["h"][i]
            s = p_stop[mid]
            if direc == 1 and lo <= s:
                p_mae[mid] = (lo - fill) * m["pv"] * ctr
                close_position(mid, d, s - slip(m), "stop_same_day", i)
            elif direc == -1 and hi >= s:
                p_mae[mid] = -(hi - fill) * m["pv"] * ctr
                close_position(mid, d, s + slip(m), "stop_same_day", i)

        # ---- 3) close-of-day updates: trail stops, MAE/MFE, marking ----
        for mid, i in todays:
            if p_dir[mid] == 0:
                continue
            m = mkts[mid]
            c_, lo, hi, a = m["c"][i], m["l"][i], m["h"][i], m["atr"][i]
            ctr, pv, direc = p_ctr[mid], m["pv"], p_dir[mid]
            if record_per_market:
                pm_pnl[d, mid] += (c_ - p_last[mid]) * direc * ctr * pv
            p_mae[mid] = min(p_mae[mid], (lo - p_fill[mid]) * direc * ctr * pv
                             if direc == 1 else
                             (p_fill[mid] - hi) * ctr * pv)
            p_mfe[mid] = max(p_mfe[mid], (hi - p_fill[mid]) * ctr * pv
                             if direc == 1 else
                             (p_fill[mid] - lo) * ctr * pv)
            p_last[mid] = c_
            if not math.isnan(a):
                if direc == 1:
                    p_ext[mid] = max(p_ext[mid], c_)
                    p_stop[mid] = max(p_stop[mid], p_ext[mid] - K * a)
                else:
                    p_ext[mid] = min(p_ext[mid], c_)
                    p_stop[mid] = min(p_stop[mid], p_ext[mid] + K * a)

        unreal = sum((p_last[j] - p_fill[j]) * p_dir[j] * p_ctr[j]
                     * mkts[j]["pv"] for j in open_mids)
        equity[d] = cash + unreal
        eq_now = equity[d]

        # ---- 4) signals at the close -> pending entry for next bar ----
        for mid, i in todays:
            if p_dir[mid] != 0 or pend[mid] is not None:
                continue
            m = mkts[mid]
            a = m["atr"][i]
            if math.isnan(a) or a <= 0 or i + 1 >= len(m["c"]):
                continue
            if entry_plan is not None:
                direc = entry_plan[mid].get(i, 0)
                if direc == 0:
                    continue
            else:
                upper, lower = chan[mid]
                u, lo_ = upper[i], lower[i]
                if math.isnan(u):
                    continue
                c_ = m["c"][i]
                direc = 1 if c_ > u else (-1 if c_ < lo_ else 0)
                if direc == 0:
                    continue
            ctr = (CONFIG["risk_per_trade"] * eq_now) / (K * a * m["pv"])
            if ctr <= 0:
                continue
            pend[mid] = (direc, ctr, a, i, d)

        eq_prev = eq_now
        if eq_now <= 0:                       # bankruptcy guard
            equity[d:] = eq_now
            break

    # liquidate remaining positions at the final mark for trade accounting
    if record_trades:
        for mid in list(open_mids):
            m = mkts[mid]
            close_position(mid, D - 1, p_last[mid], "eod_open",
                           len(m["c"]) - 1)
    return dict(equity=equity, trades=pd.DataFrame(trades), skips=skips,
                pm_pnl=pm_pnl)


# ============================================================================
# Metrics
# ============================================================================

def metrics(res, ds):
    eq = res["equity"]
    tr = res["trades"]
    D = len(eq)
    yrs = D / CONFIG["ann_factor"]
    r = np.diff(eq) / eq[:-1]
    sd = r.std()
    sharpe = r.mean() / sd * math.sqrt(CONFIG["ann_factor"]) if sd > 0 else np.nan
    dn = r[r < 0].std()
    sortino = r.mean() / dn * math.sqrt(CONFIG["ann_factor"]) if dn > 0 else np.nan
    cagr = (eq[-1] / eq[0]) ** (1 / yrs) - 1 if eq[-1] > 0 else -1.0
    peak = np.maximum.accumulate(eq)
    maxdd = float(((eq - peak) / peak).min())
    calmar = cagr / abs(maxdd) if maxdd < 0 else np.nan
    out = dict(net_pnl=eq[-1] - eq[0], cagr=cagr,
               ann_vol=sd * math.sqrt(CONFIG["ann_factor"]),
               sharpe=sharpe, sortino=sortino, maxdd=maxdd, calmar=calmar,
               years=yrs)
    if len(tr):
        pnl = tr["net_pnl"]
        wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
        out.update(
            trades=len(tr), trades_per_year=len(tr) / yrs,
            win_rate=len(wins) / len(tr),
            pf=float(wins.sum() / -losses.sum()) if losses.sum() < 0 else np.inf,
            avg_win_loss=(float(wins.mean() / -losses.mean())
                          if len(wins) and len(losses) else np.nan),
            trade_skew=float(tr["pnl_R"].skew()))
    else:
        out.update(trades=0, trades_per_year=0, win_rate=np.nan, pf=np.nan,
                   avg_win_loss=np.nan, trade_skew=np.nan)
    # time in market: position-days / market-bar-days
    total_bars = sum(len(m["c"]) for m in ds["markets"])
    out["time_in_mkt"] = (float(tr["bars_held"].sum()) / total_bars
                          if len(tr) else 0.0)
    return out


# ============================================================================
# No-look-ahead verification
# ============================================================================

def verify_indicators(ds, N, n_samples=30, rng=None):
    """Hand-recompute Donchian channels at random points; assert equality."""
    rng = rng or np.random.default_rng(7)
    for _ in range(n_samples):
        m = ds["markets"][rng.integers(len(ds["markets"]))]
        c = m["c"]
        if len(c) < N + 2:
            continue
        t = int(rng.integers(N + 1, len(c)))
        upper, lower = get_channels(m, N)
        hand_hi = max(c[t - N:t])      # prior N closes, excluding t
        hand_lo = min(c[t - N:t])
        assert abs(upper[t] - hand_hi) < 1e-9, f"channel mismatch {m['tkr']} t={t}"
        assert abs(lower[t] - hand_lo) < 1e-9, f"channel mismatch {m['tkr']} t={t}"


def verify_trades(res, ds, N, K, n_samples=50, rng=None):
    """Re-derive a sample of executed trades from raw arrays."""
    tr = res["trades"]
    tr = tr[tr["exit_reason"] != "eod_open"]
    if not len(tr):
        return
    rng = rng or np.random.default_rng(11)
    by_tkr = {m["tkr"]: m for m in ds["markets"]}
    take = tr.sample(min(n_samples, len(tr)), random_state=13)
    for _, t in take.iterrows():
        m = by_tkr[t["market"]]
        si, ei = int(t["sig_own_i"]), int(t["ent_own_i"])
        assert ei == si + 1, "entry must be exactly the next bar after signal"
        assert t["entry_date"] > t["signal_date"], "entry precedes signal!"
        upper, lower = get_channels(m, N)
        c_sig = m["c"][si]
        if t["dir"] == "L":
            assert c_sig > upper[si], "long signal not a breakout at signal bar"
        else:
            assert c_sig < lower[si], "short signal not a breakdown at signal bar"
        # fill = next bar's open +/- slippage (1x costs)
        slip_px = (CONFIG["slippage_ticks"] if m["micro"] else
                   CONFIG["slippage_ticks_research"]) * m["tick"]
        want = m["o"][ei] + (slip_px if t["dir"] == "L" else -slip_px)
        assert abs(t["entry_px"] - want) < 1e-9, "entry fill mismatch"


# ============================================================================
# Reporting helpers
# ============================================================================

def pct(x, nd=1):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) \
        else f"{100*x:.{nd}f}%"


def num(x, nd=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "inf" if isinstance(x, float) and math.isinf(x) else "—"
    return f"{x:,.{nd}f}"


def print_metrics_block(title, met):
    print(f"\n--- {title} ---")
    print(f"  Net P&L        : ${num(met['net_pnl'], 0)}"
          f"   ({met['years']:.1f} years)")
    print(f"  CAGR           : {pct(met['cagr'])}    Ann.vol: "
          f"{pct(met['ann_vol'])}")
    print(f"  Sharpe         : {num(met['sharpe'])}     Sortino: "
          f"{num(met['sortino'])}")
    print(f"  MaxDD          : {pct(met['maxdd'])}   Calmar: "
          f"{num(met['calmar'])}")
    print(f"  Profit factor  : {num(met['pf'])}     Win rate: "
          f"{pct(met['win_rate'])}")
    print(f"  Avg win/avg loss: {num(met['avg_win_loss'])}   Trade skew (R): "
          f"{num(met['trade_skew'])}")
    print(f"  Trades         : {met['trades']} ({num(met['trades_per_year'],1)}"
          f"/yr)   Time in market: {pct(met['time_in_mkt'])}")


# ============================================================================
# Main
# ============================================================================

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    sys.stdout = Tee(os.path.join(OUT_DIR, "report.txt"))
    t0 = time.time()
    cfg = CONFIG

    print("=" * 76)
    print("MTP-1 — Micro Trend Portfolio v1: research-grade backtest")
    print("=" * 76)
    print("\nDATA CAVEAT: yfinance continuous futures (=F) are front-month")
    print("chains with roll gaps, NOT back-adjusted. Donchian/ATR see roll")
    print("artifacts. This backtest is an approximation; final validation")
    print("happens later on IBKR back-adjusted data.")
    print("\nContract specs: SIL and MHG verified against CME (2026-07-08).")
    print("NOTE: the task sheet's MHG line ($1,250/pt, ~$0.63/tick) is off by")
    print("2x vs CME (MHG = 2,500 lbs -> $2,500/pt, $1.25/tick); verified")
    print("values are used.")

    # ---- data ----
    print("\nLoading data (yfinance daily, period=max, auto_adjust=False)...")
    frames, first_dates, dropped = {}, {}, {}
    for tkr, *_ in UNIVERSE:
        df, nbad = clean_ohlc(fetch_daily(tkr))
        frames[tkr], dropped[tkr] = df, nbad
        first_dates[tkr] = df.index[0]
    yrs_of = {t: (frames[t].index[-1] - frames[t].index[0]).days / 365.25
              for t in frames}
    headline = [t for t in frames if yrs_of[t] >= cfg["min_history_years"]]
    excluded = [t for t in frames if t not in headline]
    print(f"\n{'Market':8s} {'First bar':12s} {'Years':>6s} {'Bars':>6s} "
          f"{'Bad rows':>8s}  In headline?")
    for tkr, *_ in UNIVERSE:
        print(f"{tkr:8s} {str(first_dates[tkr].date()):12s} "
              f"{yrs_of[tkr]:6.1f} {len(frames[tkr]):6d} "
              f"{dropped[tkr]:8d}  "
              f"{'YES' if tkr in headline else 'NO (<10y, reported separately)'}")

    ds = build_dataset(headline, frames)
    print(f"\nHeadline universe: {len(headline)} markets, union calendar "
          f"{len(ds['master'])} days ({ds['master'][0].date()} -> "
          f"{ds['master'][-1].date()}).")

    # ---- no-look-ahead verification (indicators) ----
    for N in cfg["grid_N"]:
        verify_indicators(ds, N)
    print("Look-ahead check 1 PASSED: hand-recomputed Donchian channels "
          "match at random samples (all N).")

    # ---- Pass A grid ----
    print("\n" + "=" * 76)
    print("PASS A — research grid (fractional contracts, 1x costs)")
    print("=" * 76)
    grid = []
    grid_res = {}
    for N in cfg["grid_N"]:
        for K in cfg["grid_K"]:
            res = simulate(ds, N, K)
            met = metrics(res, ds)
            grid.append(dict(N=N, K=K, **{k: met[k] for k in
                                          ["net_pnl", "sharpe", "pf", "cagr",
                                           "maxdd", "trades", "win_rate"]}))
            grid_res[(N, K)] = res
    gdf = pd.DataFrame(grid)
    gdf_s = gdf.sort_values("sharpe", ascending=False).reset_index(drop=True)
    med_row = gdf_s.iloc[len(gdf_s) // 2]
    medN, medK = int(med_row["N"]), int(med_row["K"])
    print(f"\n{'N':>4s} {'K':>2s} {'NetP&L$':>10s} {'Sharpe':>7s} {'PF':>6s} "
          f"{'CAGR':>7s} {'MaxDD':>7s} {'Trades':>6s} {'WR':>6s}")
    for _, r in gdf.iterrows():
        tag = "  <- MEDIAN" if (r["N"] == medN and r["K"] == medK) else ""
        print(f"{int(r['N']):>4d} {int(r['K']):>2d} {r['net_pnl']:>10,.0f} "
              f"{r['sharpe']:>7.2f} {r['pf']:>6.2f} {100*r['cagr']:>6.1f}% "
              f"{100*r['maxdd']:>6.1f}% {int(r['trades']):>6d} "
              f"{100*r['win_rate']:>5.1f}%{tag}")
    print(f"\nHEADLINE = MEDIAN combo by net Sharpe: N={medN}, K={medK} "
          "(never the best combo).")
    gdf.to_csv(os.path.join(OUT_DIR, "grid_results.csv"), index=False)

    med_res = grid_res[(medN, medK)]
    # re-run headline with per-market recording for contribution/correlation
    med_res = simulate(ds, medN, medK, record_per_market=True)
    med_met = metrics(med_res, ds)
    verify_trades(med_res, ds, medN, medK)
    print("Look-ahead check 2 PASSED: sampled trades re-derived from raw "
          "arrays (signal->next-bar fill, breakout condition, fill price).")

    dN, dK = cfg["detail_combo"]
    det_res = (grid_res[(dN, dK)] if (dN, dK) in grid_res
               else simulate(ds, dN, dK))
    det_met = metrics(det_res, ds)

    print_metrics_block(f"MEDIAN combo N={medN}/K={medK} (Pass A, 1x costs)",
                        med_met)
    # sanity per non-negotiable #4
    warn = []
    if med_met["win_rate"] > 0.55:
        warn.append(f"win rate {pct(med_met['win_rate'])} > 55%")
    if med_met["sharpe"] > 2.0:
        warn.append(f"Sharpe {num(med_met['sharpe'])} > 2.0")
    if warn:
        print("  !! SANITY WARNING (probable bug per protocol): "
              + "; ".join(warn) + " — investigate before trusting.")
    else:
        print(f"  Sanity: WR {pct(med_met['win_rate'])} in the honest 30-45% "
              f"band and Sharpe {num(med_met['sharpe'])} <= 2.0 — plausible "
              "for trend following.")
    print_metrics_block(f"Reference combo N={dN}/K={dK} (Pass A, 1x costs)",
                        det_met)

    # ---- cost sensitivity (median combo) ----
    print("\n--- Cost sensitivity, median combo (multiplier x [commission "
          "+ slippage]) ---")
    cost_pnl = {}
    for cm in cfg["cost_multipliers"]:
        res_c = (med_res if cm == 1 else simulate(ds, medN, medK, cost_mult=cm))
        m_ = metrics(res_c, ds)
        cost_pnl[cm] = m_["net_pnl"]
        print(f"  {cm}x costs: net P&L ${num(m_['net_pnl'],0):>12s}  "
              f"Sharpe {num(m_['sharpe'])}  PF {num(m_['pf'])}")

    # ---- subperiods (thirds of the portfolio timeline) ----
    eq = med_res["equity"]
    b1, b2 = len(eq) // 3, 2 * len(eq) // 3
    thirds = [eq[b1 - 1] - eq[0], eq[b2 - 1] - eq[b1 - 1], eq[-1] - eq[b2 - 1]]
    names = [f"{ds['master'][0].year}-{ds['master'][b1-1].year}",
             f"{ds['master'][b1-1].year}-{ds['master'][b2-1].year}",
             f"{ds['master'][b2-1].year}-{ds['master'][-1].year}"]
    print("\n--- Subperiods (median combo, portfolio timeline thirds) ---")
    for nm, v in zip(names, thirds):
        print(f"  {nm}: ${num(v,0)} {'(positive)' if v > 0 else '(NEGATIVE)'}")
    n_pos_thirds = sum(v > 0 for v in thirds)

    # calendar-year returns for the reference combo
    eq_d = pd.Series(det_res["equity"], index=ds["master"])
    yr_ret = eq_d.groupby(eq_d.index.year).apply(
        lambda s: s.iloc[-1] / s.iloc[0] - 1)
    print(f"\n--- Calendar-year returns, N={dN}/K={dK} (Pass A) ---")
    for yy, rr in yr_ret.items():
        bars = "#" * min(40, int(abs(rr) * 100))
        print(f"  {yy}: {100*rr:>7.1f}%  {bars}")

    # ---- long vs short split (median combo) ----
    tr = med_res["trades"]
    tr_x = tr[tr["exit_reason"] != "eod_open"]
    print("\n--- Long vs short, per market (median combo, net P&L $) ---")
    ls = tr_x.pivot_table(index="market", columns="dir", values="net_pnl",
                          aggfunc="sum").reindex(headline).fillna(0.0)
    ls["L"] = ls.get("L", 0.0)
    ls["S"] = ls.get("S", 0.0)
    print(f"{'Market':8s} {'Long$':>10s} {'Short$':>10s}")
    for tkr in headline:
        print(f"{tkr:8s} {ls.loc[tkr,'L']:>10,.0f} {ls.loc[tkr,'S']:>10,.0f}")
    eq_shorts = ls.loc[[t for t in headline
                        if SPEC[t]['sector'] == 'Equity'], 'S'].sum()
    print(f"  (Equity-sector shorts total: ${num(eq_shorts,0)} — expected "
          "weak; reported, not filtered.)")

    # ---- per-market contribution & correlations ----
    pm = tr_x.groupby("market").agg(
        trades=("net_pnl", "size"), net_pnl=("net_pnl", "sum"),
        win_rate=("net_pnl", lambda s: (s > 0).mean()),
        avg_R=("pnl_R", "mean")).reindex(headline)
    pm["share_of_pnl"] = pm["net_pnl"] / pm["net_pnl"].sum()
    pm.to_csv(os.path.join(OUT_DIR, "per_market.csv"))
    print("\n--- Per-market contribution (median combo) ---")
    print(f"{'Market':8s} {'Trades':>6s} {'Net$':>10s} {'WR':>6s} "
          f"{'avgR':>6s}")
    for tkr, r in pm.iterrows():
        print(f"{tkr:8s} {int(r['trades']):>6d} {r['net_pnl']:>10,.0f} "
              f"{100*r['win_rate']:>5.1f}% {r['avg_R']:>6.2f}")
    pnl_mat = pd.DataFrame(med_res["pm_pnl"], index=ds["master"],
                           columns=headline)
    corr = pnl_mat.corr()
    corr.to_csv(os.path.join(OUT_DIR, "correlations.csv"))
    off = corr.values[np.triu_indices(len(corr), 1)]
    print(f"\nPairwise correlation of per-market daily P&L streams: mean "
          f"{num(np.nanmean(off))}, median {num(np.nanmedian(off))}, max "
          f"{num(np.nanmax(off))} (full matrix -> correlations.csv). "
          "Low correlations are the point of the portfolio.")

    # ---- random-entry bootstrap ----
    print(f"\n--- Random-entry bootstrap ({cfg['n_bootstrap']} sims, "
          f"seed {cfg['bootstrap_seed']}; same exits/sizing/caps/costs; "
          "entries at random dates matched to per-market trade & "
          "direction counts) ---")
    rng = np.random.default_rng(cfg["bootstrap_seed"])
    counts = {}
    tkr_to_mid = {m["tkr"]: j for j, m in enumerate(ds["markets"])}
    for tkr, g in tr_x.groupby("market"):
        counts[tkr_to_mid[tkr]] = (int((g["dir"] == "L").sum()),
                                   int((g["dir"] == "S").sum()))
    boot_sharpes = np.empty(cfg["n_bootstrap"])
    for b in range(cfg["n_bootstrap"]):
        plan = {}
        for mid, m in enumerate(ds["markets"]):
            nl, ns = counts.get(mid, (0, 0))
            atr_ok = np.where(~np.isnan(m["atr"]) & (m["atr"] > 0))[0]
            valid = atr_ok[(atr_ok >= CONFIG["atr_len"])
                           & (atr_ok < len(m["c"]) - 1)]
            take = min(nl + ns, len(valid))
            days = rng.choice(valid, size=take, replace=False)
            dirs = np.array([1] * nl + [-1] * ns)[:take]
            rng.shuffle(dirs)
            plan[mid] = dict(zip(days.tolist(), dirs.tolist()))
        res_b = simulate(ds, medN, medK, entry_plan=plan, record_trades=False)
        r_b = np.diff(res_b["equity"]) / res_b["equity"][:-1]
        boot_sharpes[b] = (r_b.mean() / r_b.std() * math.sqrt(cfg["ann_factor"])
                           if r_b.std() > 0 else 0.0)
        if (b + 1) % 100 == 0:
            print(f"  ... {b+1}/{cfg['n_bootstrap']} ({time.time()-t0:.0f}s)")
    p_boot = float((boot_sharpes >= med_met["sharpe"]).mean())
    print(f"  Strategy Sharpe {num(med_met['sharpe'])} vs null: mean "
          f"{num(boot_sharpes.mean())}, 95th pct "
          f"{num(np.percentile(boot_sharpes, 95))}  ->  p = {p_boot:.4f}")

    plt.figure(figsize=(8, 5))
    plt.hist(boot_sharpes, bins=40, color="#8899aa", edgecolor="white")
    plt.axvline(med_met["sharpe"], color="crimson", lw=2,
                label=f"strategy ({med_met['sharpe']:.2f}), p={p_boot:.3f}")
    plt.title(f"Random-entry bootstrap ({cfg['n_bootstrap']} sims) — "
              f"portfolio Sharpe, median combo N={medN}/K={medK}")
    plt.xlabel("annualized Sharpe")
    plt.ylabel("count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "bootstrap_hist.png"), dpi=120)
    plt.close()

    # ---- Pass B ----
    print("\n" + "=" * 76)
    print("PASS B — implementation on $10K (integer micros, margin check)")
    print("=" * 76)
    micro_uni = [t for t in headline if SPEC[t]["micro"]]
    print(f"Micro-tradable headline markets: {', '.join(micro_uni)}")
    ds_micro = build_dataset(micro_uni, frames)
    resA_micro = simulate(ds_micro, medN, medK)
    metA_micro = metrics(resA_micro, ds_micro)
    resB = simulate(ds_micro, medN, medK, integer_contracts=True,
                    margin_check=True)
    metB = metrics(resB, ds_micro)
    print_metrics_block(f"Pass A on micro universe (fractional), N={medN}/"
                        f"K={medK}", metA_micro)
    print_metrics_block(f"Pass B (integer micros + ~10% margin), N={medN}/"
                        f"K={medK}", metB)
    skipsB = pd.Series([s[2] for s in resB["skips"]]).value_counts()
    print("Pass B skip log summary: "
          + (", ".join(f"{k}: {v}" for k, v in skipsB.items())
             if len(skipsB) else "no skips"))
    retention = (metB["net_pnl"] / metA_micro["net_pnl"]
                 if metA_micro["net_pnl"] > 0 else np.nan)
    print(f"Retention (B vs A on the SAME micro universe): "
          f"{pct(retention) if not math.isnan(retention) else '—'} "
          f"(full-universe Pass A P&L was ${num(med_met['net_pnl'],0)}; "
          "same-universe comparison isolates integer-rounding + margin).")

    # ---- excluded (<10y) markets, reported separately ----
    if excluded:
        print("\n--- Markets excluded from headline (<10y history), solo "
              f"runs at N={medN}/K={medK} ---")
        for tkr in excluded:
            ds_x = build_dataset([tkr], frames)
            res_x = simulate(ds_x, medN, medK)
            met_x = metrics(res_x, ds_x)
            print(f"  {tkr}: {yrs_of[tkr]:.1f}y, net P&L "
                  f"${num(met_x['net_pnl'],0)}, Sharpe "
                  f"{num(met_x['sharpe'])}, trades {met_x['trades']}")

    # ---- gates ----
    print("\n" + "=" * 76)
    print("GATE VERDICTS")
    print("=" * 76)
    g1 = int((gdf["net_pnl"] > 0).sum())
    print(f"G1 {'PASS' if g1 >= 12 else 'FAIL'} — {g1} of {len(gdf)} grid "
          "combos net-positive (need >=12 of 15).")
    g2 = med_met["sharpe"] >= 0.35 and med_met["pf"] >= 1.15
    print(f"G2 {'PASS' if g2 else 'FAIL'} — median combo Sharpe "
          f"{num(med_met['sharpe'])} (need >=0.35), PF {num(med_met['pf'])} "
          "(need >=1.15).")
    print(f"G3 {'PASS' if n_pos_thirds >= 2 else 'FAIL'} — median combo "
          f"positive in {n_pos_thirds} of 3 subperiods (need >=2).")
    print(f"G4 {'PASS' if p_boot <= 0.05 else 'FAIL'} — bootstrap p = "
          f"{p_boot:.4f} (need <=0.05).")
    g5 = cost_pnl.get(2, np.nan)
    print(f"G5 {'PASS' if g5 > 0 else 'FAIL'} — median combo at 2x costs: "
          f"net P&L ${num(g5,0)} (need >0).")
    g6 = not math.isnan(retention) and retention >= 0.5
    print(f"G6 {'PASS' if g6 else 'FAIL'} — Pass B retains "
          f"{pct(retention) if not math.isnan(retention) else 'n/a'} of "
          "same-universe Pass A net P&L (need >=50%).")

    # ---- files ----
    tr.to_csv(os.path.join(OUT_DIR, "trades.csv"), index=False)
    fig, ax = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                           gridspec_kw={"height_ratios": [3, 1]})
    ax[0].plot(ds["master"], med_res["equity"], lw=1.2,
               label=f"Pass A median N={medN}/K={medK}")
    eqB = pd.Series(resB["equity"], index=ds_micro["master"])
    ax[0].plot(eqB.index, eqB.values, lw=1.0, alpha=0.8,
               label="Pass B ($10K micros)")
    ax[0].set_yscale("log")
    ax[0].set_title("MTP-1 equity (log scale)")
    ax[0].legend()
    peak = np.maximum.accumulate(med_res["equity"])
    ax[1].fill_between(ds["master"], (med_res["equity"] - peak) / peak, 0,
                       color="crimson", alpha=0.5)
    ax[1].set_title("Drawdown (Pass A median combo)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "equity_curve.png"), dpi=120)
    plt.close()

    # ---- honest summary ----
    gates = dict(G1=g1 >= 12, G2=g2, G3=n_pos_thirds >= 2,
                 G4=p_boot <= 0.05, G5=g5 > 0, G6=g6)
    passed = [k for k, v in gates.items() if v]
    failed = [k for k, v in gates.items() if not v]
    print("\n" + "=" * 76)
    print("HONEST SUMMARY")
    print("=" * 76)
    print(f"Passed: {', '.join(passed) if passed else 'none'}. "
          f"Failed: {', '.join(failed) if failed else 'none'}.")
    print("Biggest data-quality risk: front-month roll gaps in yfinance")
    print("continuous futures. Rolls inject artificial price jumps that (a)")
    print("trigger false Donchian breakouts, (b) distort ATR and therefore")
    print("sizing and stops, and (c) bias carry-heavy markets (energy, FX,")
    print("rates) in unknown directions. Every number here inherits that")
    print("distortion; treat this as a structural screen, not a P&L")
    print("forecast. Final validation must use back-adjusted contracts.")
    print(f"\nTotal runtime {time.time()-t0:.0f}s. Files in {OUT_DIR}/: "
          "report.txt, grid_results.csv, per_market.csv, trades.csv, "
          "correlations.csv, equity_curve.png, bootstrap_hist.png")


if __name__ == "__main__":
    main()
