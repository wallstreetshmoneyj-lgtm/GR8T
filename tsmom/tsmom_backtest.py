"""TSMOM (time-series momentum) robustness search across FX / futures / crypto.

Spec (fixed up front, no peeking):
  * Signal: sign of trailing L-day return, L in {10,20,40,60,120,180,250},
    plus a multi-horizon composite = mean of sign(20), sign(60), sign(120), sign(250).
  * Sizing: (a) fixed +/-1 (composite is fractional in [-1,1]);
            (b) vol-scaled: sign * min(3, 15% / trailing 60d realized vol).
  * Daily rebalance. Position formed at close t earns the t -> t+1 return.
  * Costs (net = gross - cost): per unit of turnover |pos_t - pos_{t-1}|:
    FX 1bp, futures 2bp, crypto 20bp.
  * Stage 1: trailing 5y/3y/1y windows (calendar cutoffs from each series' end).
  * Stage 2: per-instrument 70/30 chronological split. Selection uses IS only;
    the selected configs are then run once on OOS. Signals may warm up on
    pre-OOS prices (no selection leakage, just lookback warm-up).
  * Multiple-testing: trial count N, full distribution of stage-1 5y net
    Sharpes, Deflated Sharpe (Bailey & Lopez de Prado) for top configs, and
    the expected number of configs beating net Sharpe 0.5 by chance.

Data: Yahoo Finance daily bars, ~7y requested so the 5y window has full 250d
warm-up. yfinance is probed first; if its curl_cffi transport can't pass the
sandbox proxy, an equivalent requests-based Yahoo chart-API fetcher is used.
Yahoo continuous futures (=F) are front-month with roll gaps — a known caveat
for slow signals like TSMOM; flagged in the summary.

Run:  .venv/bin/python tsmom_backtest.py     (writes RESULTS.md + tsmom_results.csv)
"""
from __future__ import annotations

import json
import math
import sys
import time
import warnings

import numpy as np
import pandas as pd
from scipy import stats as sps

warnings.filterwarnings("ignore")

# ----------------------------------------------------------------------------- #
# configuration
# ----------------------------------------------------------------------------- #
FX = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
      "EURGBP", "EURJPY", "GBPJPY", "EURCHF", "AUDJPY"]
FUT = ["ES", "NQ", "YM", "RTY", "GC", "SI", "HG", "CL", "NG", "ZB", "ZN",
       "ZC", "ZS", "ZW", "6E", "6J"]
CRYPTO = ["BTC", "ETH", "BNB", "XRP", "ADA", "SOL", "DOGE", "LTC", "LINK",
          "DOT", "AVAX", "MATIC"]

UNIVERSE = (
    [(f"{s}=X", s, "forex") for s in FX]
    + [(f"{s}=F", s, "futures") for s in FUT]
    + [(f"{s}-USD", s, "crypto") for s in CRYPTO]
)

LOOKBACKS = [10, 20, 40, 60, 120, 180, 250]
COMPOSITE_LEGS = [20, 60, 120, 250]
SIGNALS = [str(L) for L in LOOKBACKS] + ["composite"]
SIZINGS = ["fixed", "vol"]

COST = {"forex": 0.0001, "futures": 0.0002, "crypto": 0.0020}   # per unit turnover
AF = {"forex": 252, "futures": 252, "crypto": 365}              # annualization
TARGET_VOL, MAX_LEV, VOL_WIN = 0.15, 3.0, 60
WINDOWS = {"5y": 1826, "3y": 1096, "1y": 366}                   # calendar days
RANGE = "7y"          # extra year = full 250d warm-up before the 5y window
STALE_DAYS = 21       # drop series whose last bar is this stale vs universe max
MIN_ROWS = 400        # need 250d lookback + a meaningful evaluation stretch
IS_FRAC = 0.70

# ----------------------------------------------------------------------------- #
# data
# ----------------------------------------------------------------------------- #
def _fetch_direct(ticker: str) -> pd.Series | None:
    """Yahoo v8 chart API via requests (proxy-friendly fallback for yfinance)."""
    import requests
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": "1d", "range": RANGE}
    hdrs = {"User-Agent": "Mozilla/5.0 (compatible; GR8T-TSMOM/1.0)"}
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=hdrs, timeout=30)
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            ts = res.get("timestamp")
            close = res["indicators"]["quote"][0].get("close")
            if not ts or close is None:
                return None
            idx = pd.to_datetime(ts, unit="s", utc=True).normalize().tz_localize(None)
            s = pd.Series(close, index=idx, dtype=float).dropna()
            s = s[~s.index.duplicated(keep="last")].sort_index()
            return s if len(s) else None
        except Exception:
            time.sleep(2 ** attempt)
    return None


def _probe_yfinance() -> bool:
    try:
        import yfinance as yf
        df = yf.download("EURUSD=X", period="5d", interval="1d",
                         progress=False, auto_adjust=False)
        return df is not None and len(df) > 0
    except Exception:
        return False


def load_universe():
    use_yf = _probe_yfinance()
    print(f"data transport: {'yfinance' if use_yf else 'direct chart API (yfinance blocked by proxy TLS)'}")
    prices, dropped = {}, []
    if use_yf:
        import yfinance as yf
    for ticker, name, grp in UNIVERSE:
        s = None
        if use_yf:
            try:
                df = yf.download(ticker, period=RANGE, interval="1d",
                                 progress=False, auto_adjust=False)
                if df is not None and len(df):
                    c = df["Close"]
                    c = c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c
                    s = c.dropna()
                    s.index = pd.to_datetime(s.index).normalize().tz_localize(None)
            except Exception:
                s = None
        if s is None or not len(s):
            s = _fetch_direct(ticker)
        if s is None or len(s) < MIN_ROWS:
            dropped.append((name, grp, f"insufficient data ({0 if s is None else len(s)} rows)"))
            continue
        prices[name] = (s, grp)
    if not prices:
        sys.exit("no data loaded")
    maxd = max(s.index[-1] for s, _ in prices.values())
    for name in list(prices):
        s, grp = prices[name]
        if (maxd - s.index[-1]).days > STALE_DAYS:
            dropped.append((name, grp, f"stale (last bar {s.index[-1].date()})"))
            del prices[name]
    return prices, dropped, maxd


# ----------------------------------------------------------------------------- #
# strategy construction
# ----------------------------------------------------------------------------- #
def build_positions(close: pd.Series, af: int) -> dict[tuple[str, str], pd.Series]:
    """{(signal, sizing): position series}. Position at index t is formed from
    data up to and including close t (applied to the t -> t+1 return later)."""
    rets = close.pct_change()
    vol_ann = rets.rolling(VOL_WIN).std() * math.sqrt(af)
    lev = (TARGET_VOL / vol_ann).clip(upper=MAX_LEV)
    lev = lev.where(np.isfinite(lev), 0.0).fillna(0.0)

    signs = {L: np.sign(close / close.shift(L) - 1.0) for L in LOOKBACKS}
    comp = pd.concat([signs[L] for L in COMPOSITE_LEGS], axis=1).mean(axis=1, skipna=False)

    out = {}
    for name, sig in [(str(L), signs[L]) for L in LOOKBACKS] + [("composite", comp)]:
        sig = sig.fillna(0.0)
        out[(name, "fixed")] = sig
        out[(name, "vol")] = sig * lev
    return out


def strat_returns(close: pd.Series, pos: pd.Series, cost: float):
    """(gross, net, pos) daily series. net_t = pos_{t-1}*ret_t - cost*|dpos_t|."""
    rets = close.pct_change().fillna(0.0)
    gross = pos.shift(1).fillna(0.0) * rets
    net = gross - cost * pos.diff().abs().fillna(0.0)
    return gross, net


def metrics(gross: pd.Series, net: pd.Series, pos: pd.Series, af: int) -> dict:
    n = len(net)
    if n < 30 or net.std() == 0:
        return {}
    active = pos.shift(1).reindex(net.index).fillna(0.0) != 0
    na = net[active]
    eq = (1 + net).cumprod()
    peak = eq.cummax()
    wins, losses = na[na > 0], na[na < 0]
    out = {
        "n_days": n,
        "sharpe_gross": gross.mean() / gross.std() * math.sqrt(af) if gross.std() > 0 else 0.0,
        "sharpe_net": net.mean() / net.std() * math.sqrt(af),
        "ann_ret_gross": (1 + gross).prod() ** (af / n) - 1,
        "ann_ret_net": eq.iloc[-1] ** (af / n) - 1,
        "ann_vol": net.std() * math.sqrt(af),
        "max_dd_net": (1 - eq / peak).max(),
        "win_rate": (na > 0).mean() if len(na) else np.nan,
        "profit_factor": (wins.sum() / -losses.sum()) if losses.sum() < 0 else np.inf,
        "t_stat_net": net.mean() / net.std() * math.sqrt(n),
        "turnover_ann": pos.diff().abs().mean() * af,
        "af": af,
    }
    return out


def window_slices(index: pd.DatetimeIndex):
    """{window: boolean mask} for 5y/3y/1y calendar windows + IS/OOS split."""
    end = index[-1]
    masks = {w: index >= (end - pd.Timedelta(days=d)) for w, d in WINDOWS.items()}
    cut = int(len(index) * IS_FRAC)
    masks["IS"] = np.arange(len(index)) < cut
    masks["OOS"] = np.arange(len(index)) >= cut
    masks["full"] = np.ones(len(index), bool)
    return masks


# ----------------------------------------------------------------------------- #
# deflated Sharpe (Bailey & Lopez de Prado 2014)
# ----------------------------------------------------------------------------- #
EULER = 0.5772156649


def deflated_sharpe(net: pd.Series, af: int, n_trials: int, var_trials_ann: float):
    """Returns (PSR, DSR, SR0_ann). All Sharpe math done per-period, reported
    annualized. DSR = P(true SR > 0) after penalising for N selection trials
    whose measured Sharpes have variance var_trials_ann (annualized units)."""
    n = len(net)
    sr_p = net.mean() / net.std()                       # per-period Sharpe
    var_p = var_trials_ann / af                          # trial variance, per-period
    z1 = sps.norm.ppf(1 - 1.0 / n_trials)
    z2 = sps.norm.ppf(1 - 1.0 / (n_trials * math.e))
    sr0_p = math.sqrt(max(var_p, 1e-12)) * ((1 - EULER) * z1 + EULER * z2)
    g3 = sps.skew(net)
    g4 = sps.kurtosis(net, fisher=False)
    denom = math.sqrt(max(1 - g3 * sr_p + (g4 - 1) / 4 * sr_p ** 2, 1e-12))
    psr = sps.norm.cdf(sr_p * math.sqrt(n - 1) / denom)
    dsr = sps.norm.cdf((sr_p - sr0_p) * math.sqrt(n - 1) / denom)
    return psr, dsr, sr0_p * math.sqrt(af)


# ----------------------------------------------------------------------------- #
# main
# ----------------------------------------------------------------------------- #
def main():
    t0 = time.time()
    prices, dropped, maxd = load_universe()
    groups = sorted({g for _, g in prices.values()})
    print(f"loaded {len(prices)} instruments (latest bar {maxd.date()}); dropped: "
          f"{[(n, r) for n, _, r in dropped] or 'none'}")

    rows = []            # CSV rows
    nets = {}            # (sym, signal, sizing) -> (gross, net, pos, af, group)

    # ---- per-instrument configs -------------------------------------------- #
    for sym, (close, grp) in prices.items():
        af, cost = AF[grp], COST[grp]
        poss = build_positions(close, af)
        masks = window_slices(close.index)
        for (signal, sizing), pos in poss.items():
            gross, net = strat_returns(close, pos, cost)
            nets[(sym, signal, sizing)] = (gross, net, pos, af, grp)
            for w, m in masks.items():
                mt = metrics(gross[m], net[m], pos[m], af)
                if mt:
                    rows.append({"level": "instrument", "group": grp, "instrument": sym,
                                 "signal": signal, "sizing": sizing, "window": w, **mt})
        # buy & hold reference (long 1x, no rebalancing turnover)
        bh_pos = pd.Series(1.0, index=close.index)
        g_bh, n_bh = strat_returns(close, bh_pos, cost)
        for w, m in masks.items():
            mt = metrics(g_bh[m], n_bh[m], bh_pos[m], af)
            if mt:
                rows.append({"level": "instrument", "group": grp, "instrument": sym,
                             "signal": "buyhold", "sizing": "long1x", "window": w, **mt})

    # ---- group portfolios (equal-weight member strategy returns) ------------ #
    group_nets = {}      # (grp, signal, sizing) -> (gross, net, pos_proxy, af)
    for grp in groups:
        members = [s for s, (_, g) in prices.items() if g == grp]
        af = AF[grp]
        for signal in SIGNALS:
            for sizing in SIZINGS:
                gs = pd.concat([nets[(m, signal, sizing)][0] for m in members], axis=1)
                ns = pd.concat([nets[(m, signal, sizing)][1] for m in members], axis=1)
                ps = pd.concat([nets[(m, signal, sizing)][2] for m in members], axis=1)
                enough = ns.notna().sum(axis=1) >= max(3, len(members) // 3)
                gross = gs.mean(axis=1)[enough]
                net = ns.mean(axis=1)[enough]
                pos = ps.abs().mean(axis=1)[enough]      # exposure proxy for turnover/active
                group_nets[(grp, signal, sizing)] = (gross, net, pos, af)
                masks = window_slices(net.index)
                for w, m in masks.items():
                    mt = metrics(gross[m], net[m], pos[m], af)
                    if mt:
                        rows.append({"level": "group", "group": grp, "instrument": f"EW-{grp}",
                                     "signal": signal, "sizing": sizing, "window": w, **mt})
        # group buy & hold (equal-weight long members)
        bh = pd.concat([prices[m][0].pct_change() for m in members], axis=1).mean(axis=1).dropna()
        bh_pos = pd.Series(1.0, index=bh.index)
        masks = window_slices(bh.index)
        for w, m in masks.items():
            mt = metrics(bh[m], bh[m], bh_pos[m], af)
            if mt:
                rows.append({"level": "group", "group": grp, "instrument": f"EW-{grp}",
                             "signal": "buyhold", "sizing": "long1x", "window": w, **mt})

    df = pd.DataFrame(rows)
    df.to_csv("tsmom_results.csv", index=False, float_format="%.6f")

    # ======================================================================== #
    # summaries
    # ======================================================================== #
    md = ["# TSMOM robustness search — results",
          f"\nLatest bar: **{maxd.date()}** · instruments loaded: **{len(prices)}** · "
          f"costs per unit turnover: fx 1bp / fut 2bp / crypto 20bp · "
          f"sizing 'vol' = 15% target, 60d realized, 3x cap.",
          f"\nDropped instruments: " +
          ("; ".join(f"{n} ({r})" for n, _, r in dropped) if dropped else "none") + "."]

    # ---- (a) per-instrument ranked table (composite, vol-scaled) ------------ #
    inst = df[(df.level == "instrument") & (df.signal == "composite") & (df.sizing == "vol")]
    piv = inst.pivot_table(index=["group", "instrument"], columns="window",
                           values="sharpe_net").reset_index()
    for w in ["5y", "3y", "1y"]:
        if w not in piv:
            piv[w] = np.nan
    piv["flag"] = np.where((piv["5y"] > 0) & (piv["3y"] > 0) & (piv["1y"] > 0),
                           "CONSISTENT", "FRAGILE")
    piv = piv.sort_values("5y", ascending=False)
    md.append("\n## (a) Stage 1 — per-instrument net Sharpe (multi-horizon composite, vol-scaled)\n")
    md.append("| instrument | group | net Sharpe 5y | 3y | 1y | flag |")
    md.append("|---|---|---|---|---|---|")
    for _, r in piv.iterrows():
        md.append(f"| {r['instrument']} | {r['group']} | {r['5y']:+.2f} | "
                  f"{r['3y']:+.2f} | {r['1y']:+.2f} | {r['flag']} |")

    # ---- (b) group x lookback x window ------------------------------------- #
    gv = df[(df.level == "group") & (df.sizing == "vol") & (df.signal != "buyhold")]
    md.append("\n## (b) Stage 1 — group portfolios (vol-scaled, net Sharpe)\n")
    md.append("| group | signal | 5y | 3y | 1y |")
    md.append("|---|---|---|---|---|")
    best_gl = {}
    for grp in groups:
        for signal in SIGNALS:
            sub = gv[(gv.group == grp) & (gv.signal == signal)]
            vals = {w: sub[sub.window == w]["sharpe_net"] for w in ["5y", "3y", "1y"]}
            v = {w: (x.iloc[0] if len(x) else np.nan) for w, x in vals.items()}
            best_gl[(grp, signal)] = v["5y"]
            md.append(f"| {grp} | {signal} | {v['5y']:+.2f} | {v['3y']:+.2f} | {v['1y']:+.2f} |")
    best_row = max(((k, v) for k, v in best_gl.items() if np.isfinite(v)), key=lambda kv: kv[1])
    md.append(f"\nBest group config in-sample-recent (5y): **{best_row[0][0]} @ signal "
              f"{best_row[0][1]}** with net Sharpe {best_row[1]:+.2f}.")

    # ---- Stage 2: IS selection -> OOS validation ---------------------------- #
    md.append("\n## (c) Stage 2 — out-of-sample validation (selection on oldest 70% only)\n")
    md.append("| config | IS net Sharpe | OOS net Sharpe | degradation | OOS ann ret | OOS maxDD | OOS t-stat |")
    md.append("|---|---|---|---|---|---|---|")
    gis = df[(df.level == "group") & (df.sizing == "vol") & (df.signal != "buyhold")]
    selected = []
    for grp in groups:
        sub = gis[(gis.group == grp) & (gis.window == "IS") & gis.signal.isin([str(L) for L in LOOKBACKS])]
        if not len(sub):
            continue
        bi = sub.loc[sub.sharpe_net.idxmax()]
        selected.append((f"{grp} @ L={bi.signal} (group, vol)", grp, bi.signal))
    sub_all = gis[gis.window == "IS"]
    bo = sub_all.loc[sub_all.sharpe_net.idxmax()]
    selected.append((f"BEST OVERALL: {bo.group} @ {bo.signal} (group, vol)", bo.group, bo.signal))
    # top-3 instruments on IS (composite, vol)
    iis = df[(df.level == "instrument") & (df.signal == "composite") &
             (df.sizing == "vol") & (df.window == "IS")].nlargest(3, "sharpe_net")
    inst_sel = [(f"{r.instrument} composite (instrument, vol)", r.instrument) for _, r in iis.iterrows()]

    dsr_candidates = []
    for label, grp, signal in selected:
        isr = gis[(gis.group == grp) & (gis.signal == signal) & (gis.window == "IS")]["sharpe_net"].iloc[0]
        osub = gis[(gis.group == grp) & (gis.signal == signal) & (gis.window == "OOS")]
        if not len(osub):
            continue
        o = osub.iloc[0]
        md.append(f"| {label} | {isr:+.2f} | {o.sharpe_net:+.2f} | {o.sharpe_net - isr:+.2f} | "
                  f"{o.ann_ret_net * 100:+.1f}% | {o.max_dd_net * 100:.1f}% | {o.t_stat_net:+.2f} |")
        dsr_candidates.append((label, group_nets[(grp, signal, "vol")][1], AF[grp], "5y"))
    for label, sym in inst_sel:
        i_is = df[(df.level == "instrument") & (df.instrument == sym) & (df.signal == "composite") &
                  (df.sizing == "vol") & (df.window == "IS")]["sharpe_net"].iloc[0]
        oo = df[(df.level == "instrument") & (df.instrument == sym) & (df.signal == "composite") &
                (df.sizing == "vol") & (df.window == "OOS")]
        if not len(oo):
            continue
        o = oo.iloc[0]
        md.append(f"| {label} | {i_is:+.2f} | {o.sharpe_net:+.2f} | {o.sharpe_net - i_is:+.2f} | "
                  f"{o.ann_ret_net * 100:+.1f}% | {o.max_dd_net * 100:.1f}% | {o.t_stat_net:+.2f} |")
        g, n_, p_, afc, _ = nets[(sym, "composite", "vol")]
        dsr_candidates.append((label, n_, afc, "5y"))

    # ---- multiple-testing block --------------------------------------------- #
    stage1 = df[(df.window == "5y") & (df.signal != "buyhold")]
    n_trials = len(stage1)
    dist = stage1["sharpe_net"]
    var_trials_ann = float(dist.var())
    md.append("\n## (d) Multiple-testing accounting\n")
    md.append(f"* Total configs tested (stage-1 5y rows, instrument + group, both sizings): "
              f"**N = {n_trials}**")
    md.append(f"* Stage-1 net-Sharpe distribution: mean {dist.mean():+.2f}, median {dist.median():+.2f}, "
              f"std {dist.std():.2f}, 5th pct {dist.quantile(.05):+.2f}, 95th pct {dist.quantile(.95):+.2f}")
    p_chance = 1 - sps.norm.cdf(0.5 / (1 / math.sqrt(5)))
    md.append(f"* Under a zero-edge null, a 5y measured Sharpe has std ≈ 1/√5 ≈ 0.45, so "
              f"P(net Sharpe > 0.5 by chance) ≈ {p_chance * 100:.0f}% per independent trial → "
              f"≈ **{n_trials * p_chance:.0f} of {n_trials}** configs would clear 0.5 by luck alone "
              f"(fewer effective independent trials due to correlation, but the order of magnitude stands).")
    md.append(f"* Observed configs with 5y net Sharpe > 0.5: **{(dist > 0.5).sum()}**")

    md.append("\n### Regular vs Deflated Sharpe (5y net returns; N and trial variance as above)\n")
    md.append("| config | ann Sharpe (5y) | deflated Sharpe (haircut) | P(true SR > 0) after selection |")
    md.append("|---|---|---|---|")
    end_by = {}
    for label, netser, afc, w in dsr_candidates:
        mask = netser.index >= (netser.index[-1] - pd.Timedelta(days=WINDOWS["5y"]))
        n5 = netser[mask]
        if len(n5) < 100 or n5.std() == 0:
            continue
        sr_ann = n5.mean() / n5.std() * math.sqrt(afc)
        psr, dsr, sr0_ann = deflated_sharpe(n5, afc, n_trials, var_trials_ann)
        md.append(f"| {label} | {sr_ann:+.2f} | {sr_ann - sr0_ann:+.2f} | {dsr * 100:.0f}% |")

    # ---- buy & hold comparison ---------------------------------------------- #
    md.append("\n## Reference — buy & hold (5y, net Sharpe)\n")
    bh = df[(df.signal == "buyhold") & (df.window == "5y") & (df.level == "group")]
    for _, r in bh.iterrows():
        md.append(f"* EW long {r.group}: Sharpe {r.sharpe_net:+.2f}, "
                  f"ann ret {r.ann_ret_net * 100:+.1f}%, maxDD {r.max_dd_net * 100:.0f}%")

    with open("RESULTS.md", "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nwrote RESULTS.md + tsmom_results.csv ({len(df)} metric rows) "
          f"in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
