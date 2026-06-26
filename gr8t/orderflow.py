"""Experiment 4 — add a 15m volume-profile (POC) order-flow layer.

Strategy under test (the current best), on ES:
  * trend  : 1h 50-SMA
  * POIs    : same-colour imbalances on 15m & 5m (1h POIs dropped)
  * entry   : 5m engulfing / hammer / shooting-star, pro-trend, while touching/
              inside the POI
  * exit    : 1.5 x 5m-ATR stop -> break-even at 1R -> fixed 1:2 target

Order-flow layer: build a 15m volume profile over the *current range* — the most
recent swing high and the swing low that created it (and vice-versa) — and take
the point of control (POC). A trade is only allowed pro-trend AND when the POC
sits on the pullback side of the range: bullish needs POC in the lower <=70% of
the range, bearish in the upper >=30%. We then trade the imbalance the POC sits
in, or the nearest 5m/15m imbalance to it.

Everything (swings, range, profile, trend, ATR, patterns) is computed using only
data available at the entry bar — no look-ahead.

Variants compared: base (no OF) single-/multi-TF, +OF single-/multi-TF, and
POC-only. Each segmented by candle pattern, reported net of slippage.

    python -m gr8t.orderflow --symbol ES=F --report of.html
"""
from __future__ import annotations

import argparse
import numpy as np
import pandas as pd

from .config import Config
from .data import load_base, synthetic_series
from .backtest import Trade, Backtester
from .stats import compute_stats
from .indicators import find_swings, volume_profile
from .poi_lab import (_precompute_patterns, _exp_cost, _gap_bucket, PATTERNS,
                      trend_series)

POC_THRESHOLD = 0.70   # bull: POC must be in the lower <=70% of the range


# --------------------------------------------------------------------------- #
# exit: 1.5 ATR stop -> break-even at 1R -> fixed R:R target
# --------------------------------------------------------------------------- #
def _bracket_be(direction, ei, entry_time, entry, stop, target_rr, pattern, poi_tf,
                o, h, l, c, n, breakeven=True):
    risk = abs(entry - stop)
    be_level = entry + risk if direction == "bull" else entry - risk
    target = entry + target_rr * risk if direction == "bull" else entry - target_rr * risk
    tr = Trade(direction=direction, entry_index=ei, entry_time=entry_time,
               entry_price=entry, init_stop=stop, risk=risk, pattern=pattern, poi_tf=poi_tf)
    be = False
    if not breakeven:
        be_level = float("inf") if direction == "bull" else float("-inf")
    cur_stop = stop
    for j in range(ei + 1, n):
        if direction == "bull":
            if l[j] <= cur_stop:
                r = 0.0 if be else -1.0
                tr.exit_index, tr.exit_price, tr.exit_reason, tr.r_multiple = j, cur_stop, ("be" if be else "stop"), r
                tr.bars_held = j - ei
                return tr
            if not be and h[j] >= be_level:
                cur_stop, be = entry, True
            if h[j] >= target:
                tr.exit_index, tr.exit_price, tr.exit_reason, tr.r_multiple = j, target, "target", target_rr
                tr.bars_held = j - ei
                return tr
        else:
            if h[j] >= cur_stop:
                r = 0.0 if be else -1.0
                tr.exit_index, tr.exit_price, tr.exit_reason, tr.r_multiple = j, cur_stop, ("be" if be else "stop"), r
                tr.bars_held = j - ei
                return tr
            if not be and l[j] <= be_level:
                cur_stop, be = entry, True
            if l[j] <= target:
                tr.exit_index, tr.exit_price, tr.exit_reason, tr.r_multiple = j, target, "target", target_rr
                tr.bars_held = j - ei
                return tr
    px = float(c[n - 1])
    tr.exit_index, tr.exit_price, tr.exit_reason = n - 1, px, "eod"
    tr.r_multiple = (px - entry) / risk if direction == "bull" else (entry - px) / risk
    tr.bars_held = n - 1 - ei
    return tr


# --------------------------------------------------------------------------- #
# order-flow: current range + 15m POC (no look-ahead)
# --------------------------------------------------------------------------- #
def _leg_bounds(swings, as_of_index):
    """(start_index, last_high, last_low) for the current leg using only swings
    confirmed at/before as_of_index."""
    last_high = last_low = None
    for s in swings:
        if s.confirm_index > as_of_index:
            break
        if s.kind == "high":
            last_high = s
        else:
            last_low = s
    if last_high is None or last_low is None:
        return None
    return min(last_high.index, last_low.index)


def _poc_at(mid, swings, vp_bins, t, lookback):
    """(poc_price, poc_position 0..1, range_low, range_high) of the 15m profile
    over the current range as of time t, or None."""
    mid_pos = int(mid.index.searchsorted(t, side="right")) - 1
    if mid_pos < lookback * 2:
        return None
    start = _leg_bounds(swings, mid_pos)
    if start is None or start >= mid_pos:
        return None
    seg = mid.iloc[start:mid_pos + 1]
    vp = volume_profile(seg, vp_bins)
    if vp is None:
        return None
    rl, rh = float(seg["low"].min()), float(seg["high"].max())
    if rh <= rl:
        return None
    return vp.poc_price, (vp.poc_price - rl) / (rh - rl), rl, rh


# --------------------------------------------------------------------------- #
# build the base tagged trade set
# --------------------------------------------------------------------------- #
def build_trades(base: pd.DataFrame, cfg: Config, trend_mode: str = "high",
                 stop_atr: float = 1.5, target_rr: float = 2.0, breakeven: bool = True):
    cfg.require_same_color = True                 # POIs must be same colour
    bt = Backtester(base, cfg)
    strat = bt.strategy
    trend = trend_series(strat, trend_mode)

    o = base["open"].to_numpy(float); h = base["high"].to_numpy(float)
    l = base["low"].to_numpy(float); c = base["close"].to_numpy(float)
    atr_arr = strat.atr.to_numpy(float)
    n = len(base)
    bull_pat, bear_pat = _precompute_patterns(o, h, l, c, cfg)

    imbs = strat.imbalances                        # same-colour, all TFs
    # arrays for multi-TF overlap (any TF) and for nearest-to-POC (5m/15m only)
    all_arr = {tf: (np.array([z.lower for z in zs]), np.array([z.upper for z in zs]),
                    np.array([z._meta["usable_from"] for z in zs]),
                    np.array([z.direction for z in zs]))
               for tf, zs in _group(imbs).items()}
    trade_imbs = [z for z in imbs if z.tf in ("5min", "15min")]
    lo_arr = np.array([z.lower for z in trade_imbs]); up_arr = np.array([z.upper for z in trade_imbs])
    mid_arr = np.array([z.mid for z in trade_imbs]); us_arr = np.array([z._meta["usable_from"] for z in trade_imbs])
    iv_arr = np.array([z._meta["invalid_from"] for z in trade_imbs])
    dir_arr = np.array([z.direction for z in trade_imbs])

    swings = find_swings(strat.mid, cfg.swing_lookback)

    trades = []
    for idx, imb in enumerate(trade_imbs):
        d = imb.direction
        start = imb._meta["usable_from"]; inv = min(imb._meta["invalid_from"], n)
        if start >= inv:
            continue
        seg_l, seg_h, seg_t = l[start:inv], h[start:inv], trend[start:inv]
        cond = (seg_l <= imb.upper) & (seg_h >= imb.lower) & (seg_t == d)
        if not cond.any():
            continue
        pat_arr = bull_pat if d == "bull" else bear_pat
        far = imb.lower if d == "bull" else imb.upper
        ei = None
        for gi in (np.nonzero(cond)[0] + start):
            if pat_arr[gi] is None:
                continue
            ei, entry_price, pat_name = int(gi), float(c[gi]), pat_arr[gi]
            break
        if ei is None:
            continue
        a = atr_arr[ei]
        if not (np.isfinite(a) and a > 0):
            continue
        stop = entry_price - stop_atr * a if d == "bull" else entry_price + stop_atr * a
        gap_atr = (imb.upper - imb.lower) / a

        # multi-TF (same-direction overlap on another timeframe, confirmed by ei)
        mtf = False
        for tf2, (lows, ups, uss, dirs) in all_arr.items():
            if tf2 == imb.tf:
                continue
            if ((imb.lower < ups) & (lows < imb.upper) & (uss <= ei) & (dirs == d)).any():
                mtf = True
                break

        # order-flow POC at entry
        poc = _poc_at(strat.mid, swings, cfg.vp_bins, base.index[ei], cfg.swing_lookback)
        if poc is None:
            of_pass = poc_inside = poc_anchored = False
            poc_pos = None
        else:
            poc_price, poc_pos, rl, rh = poc
            of_pass = (poc_pos <= POC_THRESHOLD) if d == "bull" else (poc_pos >= 1 - POC_THRESHOLD)
            poc_inside = imb.lower <= poc_price <= imb.upper
            active = (us_arr <= ei) & (ei < iv_arr) & (dir_arr == d)
            if active.any():
                cand_idx = np.nonzero(active)[0]
                nearest = cand_idx[np.argmin(np.abs(mid_arr[cand_idx] - poc_price))]
                poc_anchored = poc_inside or (nearest == idx)
            else:
                poc_anchored = poc_inside

        tr = _bracket_be(d, ei, base.index[ei], entry_price, stop, target_rr,
                         pat_name, imb.tf, o, h, l, c, n, breakeven=breakeven)
        tr.same_color = imb.same_color
        tr.multi_tf = mtf
        tr.gap_atr = gap_atr
        tr.poi_tf = imb.tf
        tr.of_pass = of_pass
        tr.poc_inside = poc_inside
        tr.poc_anchored = poc_anchored
        tr.poc_pos = poc_pos
        trades.append(tr)
    trades.sort(key=lambda t: t.entry_index)
    return trades


def _group(imbs):
    g = {}
    for z in imbs:
        g.setdefault(z.tf, []).append(z)
    return g


# --------------------------------------------------------------------------- #
# variants + reporting
# --------------------------------------------------------------------------- #
def variants(trades):
    return {
        "base single-TF": list(trades),
        "base multi-TF": [t for t in trades if t.multi_tf],
        "+OF single-TF": [t for t in trades if t.of_pass and t.poc_anchored],
        "+OF multi-TF": [t for t in trades if t.of_pass and t.poc_anchored and t.multi_tf],
        "POC-only (in zone)": [t for t in trades if t.of_pass and t.poc_inside],
    }


def _metrics(ts, cfg):
    s = compute_stats(ts, cfg)
    if not s.get("trades"):
        return None
    e5, _ = _exp_cost(ts, 0.5)
    rate = lambda reason: float(np.mean([t.exit_reason == reason for t in ts])) * 100
    return dict(n=s["trades"], win=s["win_rate"] * 100, tgt=rate("target"), be=rate("be"),
                stop=rate("stop"), e0=s["expectancy_r"], e5=e5, pf=s["profit_factor"])


def format_compare(vmap, cfg) -> str:
    lines = [f"  variant{'':14}{'n':>5} {'win%':>6} {'tgt%':>5} {'BE%':>5} {'stop%':>6}  "
             f"{'exp@0':>7} {'exp@0.5pt':>9} {'PF':>5}"]
    lines.append("  " + "-" * 78)
    for name, ts in vmap.items():
        m = _metrics(ts, cfg)
        if not m:
            lines.append(f"  {name:20} n=0")
            continue
        lines.append(f"  {name:20}{m['n']:5d} {m['win']:6.1f} {m['tgt']:5.1f} {m['be']:5.1f} "
                     f"{m['stop']:6.1f}  {m['e0']:+7.3f} {m['e5']:+9.3f} {m['pf']:5.2f}")
    return "\n".join(lines)


def format_pattern_breakdown(vmap, cfg) -> str:
    pats = [p for p in PATTERNS if p != "touch"]
    lines = ["\n  Expectancy @0.5pt by candle pattern (n in parens)",
             f"    {'variant':20}" + "".join(f"{p.split('_')[0][:8]:>12}" for p in pats)]
    for name, ts in vmap.items():
        cells = []
        for p in pats:
            sub = [t for t in ts if t.pattern == p]
            cells.append(f"{_exp_cost(sub,0.5)[0]:+.2f}({len(sub)})" if sub else "—")
        lines.append(f"    {name:20}" + "".join(f"{c:>12}" for c in cells))
    return "\n".join(lines)


def build_report(vmap, cfg, meta, source) -> str:
    from .report import _svg_bars, _PAGE, _card
    names = list(vmap.keys())
    e0 = [round((_metrics(vmap[k], cfg) or {"e0": 0})["e0"], 3) for k in names]
    e5 = [round((_metrics(vmap[k], cfg) or {"e5": 0})["e5"], 3) for k in names]
    ns = [(_metrics(vmap[k], cfg) or {"n": 0})["n"] for k in names]

    base = _metrics(vmap["base single-TF"], cfg) or {"e5": 0, "n": 0}
    of = _metrics(vmap["+OF single-TF"], cfg) or {"e5": 0, "n": 0}
    cards = [
        _card("base (no OF) @0.5pt", f"{base['e5']:+.3f}R", "pos" if base["e5"] > 0 else "neg"),
        _card("+order flow @0.5pt", f"{of['e5']:+.3f}R", "pos" if of["e5"] > 0 else "neg"),
        _card("OF lift", f"{(of['e5']-base['e5']):+.3f}R", "pos" if of["e5"] > base["e5"] else "neg"),
        _card("OF trades vs base", f"{of['n']} / {base['n']}"),
    ]
    labels = [k.replace(" ", "\n") for k in names]
    sections = [
        ("Expectancy by variant — zero cost",
         _svg_bars(e0, ["#1f9d55" if v >= 0 else "#e3342f" for v in e0], labels=names, fmt="{:+.2f}", label_every=1)),
        ("Expectancy by variant — net 0.5pt slippage",
         _svg_bars(e5, ["#1f9d55" if v >= 0 else "#e3342f" for v in e5], labels=names, fmt="{:+.2f}", label_every=1)),
        ("Trade count by variant",
         _svg_bars([float(x) for x in ns], ["#58a6ff"] * len(ns), labels=names, fmt="{:.0f}", label_every=1)),
    ]
    charts = "".join(f"<section class='panel'><h3>{t}</h3>{svg}</section>" for t, svg in sections)

    pats = [p for p in PATTERNS if p != "touch"]
    rows = []
    for name, ts in vmap.items():
        cells = []
        for p in pats:
            sub = [t for t in ts if t.pattern == p]
            e = _exp_cost(sub, 0.5)[0] if sub else None
            cls = "pos" if (e is not None and e > 0) else "neg"
            cells.append(f"<td class='{cls}'>{e:+.3f}<br><span class='muted'>{len(sub)}</span></td>"
                         if sub else "<td>—</td>")
        rows.append(f"<tr><td class='l'>{name}</td>{''.join(cells)}</tr>")
    thead = "<th class='l'>variant</th>" + "".join(f"<th>{p.replace('_',' ')}</th>" for p in pats)
    table = (f"<section class='panel'><h3>Pattern x variant — expectancy net 0.5pt</h3>"
             f"<div class='tw'><table><thead><tr>{thead}</tr></thead><tbody>{''.join(rows)}</tbody>"
             f"</table></div></section>")

    tfs = f"{cfg.base_tf}/{cfg.mid_tf}/{cfg.high_tf}"
    subtitle = (f"order-flow study · 1h trend · same-colour 15m/5m POIs · pattern entry · "
                f"1.5 ATR stop, BE@1R, 1:2 · {meta['start']} → {meta['end']} · "
                f"{meta['n_base']} bars · {source}")
    body = f"<section class='cards'>{''.join(cards)}</section>{charts}{table}"
    return _PAGE.format(title=f"{cfg.symbol} · order-flow study", subtitle=subtitle, body=body)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Order-flow (15m POC) experiment")
    p.add_argument("--symbol", default="ES=F")
    p.add_argument("--preset", choices=list(Config.PRESETS), default="intraday")
    p.add_argument("--report", metavar="PATH")
    p.add_argument("--no-be", action="store_true", dest="no_be",
                   help="disable break-even-at-1R (pure 1:2 bracket) to isolate its effect")
    p.add_argument("--synthetic", action="store_true")
    args = p.parse_args(argv)

    cfg = Config.preset(args.preset, symbol=args.symbol)
    source = "yahoo"
    if args.synthetic:
        base = synthetic_series(n=5000); cfg.symbol = "SYNTH"; source = "synthetic"
    else:
        try:
            base = load_base(cfg)
        except Exception as e:  # noqa: BLE001
            print(f"data load failed ({e}); using synthetic"); base = synthetic_series(n=5000)
            cfg.symbol = "SYNTH"; source = "synthetic"

    meta = {"start": str(base.index[0].date()), "end": str(base.index[-1].date()), "n_base": len(base)}
    trades = build_trades(base, Config.preset(args.preset, symbol=cfg.symbol),
                          breakeven=not args.no_be)
    vmap = variants(trades)

    print(f"\nOrder-flow study — {cfg.symbol} · 1h trend · same-colour 15m/5m POIs · "
          f"pattern entry · 1.5 ATR stop, BE@1R, 1:2 target")
    print(f"{meta['start']} → {meta['end']} · {len(base)} bars")
    print("=" * 92)
    print(format_compare(vmap, cfg))
    print(format_pattern_breakdown(vmap, cfg))

    if args.report:
        with open(args.report, "w") as f:
            f.write(build_report(vmap, cfg, meta, source))
        print(f"\nWrote visual order-flow study -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
