"""POI laboratory — experiment 1: which imbalances actually work?

Loosest possible POI definition, no entry pattern, so we can isolate the POI:

  * every 3-candle gap on 1h / 15m / 5m is a POI (any colour, no MTF requirement)
  * a POI is only taken pro-trend (imbalance direction must match the trend)
  * ENTRY: the moment price taps the zone, filled at the near edge
  * STOP : the far (counter-trend) edge of the zone  -> 1R = the gap height
  * TP   : dynamic — break-even at 1:1, then the ATR trail (same as the strategy)

Every resulting trade is TAGGED with its POI's properties (timeframe, whether
the three candles were the same colour, whether it was multi-timeframe, and the
gap size in ATRs) so the results can be sliced to answer: which POIs work, and
are 'same colour' and 'multi-timeframe' actually worth requiring? Run under two
trend filters (1h, and 1h+15m) to see which pairs best with the POI.

    python -m gr8t.poi_lab --symbol ES=F --report poi.html
"""
from __future__ import annotations

import argparse
from typing import Optional

import numpy as np
import pandas as pd

from .config import Config
from .data import load_base, synthetic_series
from .backtest import Backtester, Trade
from .strategy import Signal
from .stats import compute_stats
from .patterns import (is_bullish_engulfing, is_bearish_engulfing,
                       is_hammer, is_shooting_star)


def _precompute_patterns(o, h, l, c, cfg):
    """Per-bar trend-aligned candle pattern (name or None), computed once from
    arrays so the lab stays fast. Each pattern only uses bars up to and
    including its own bar -> no look-ahead."""
    n = len(o)
    bull = np.empty(n, dtype=object); bull[:] = None
    bear = np.empty(n, dtype=object); bear[:] = None
    wr, bm, om = cfg.wick_body_ratio, cfg.body_max_frac, cfg.opp_wick_max_frac
    for i in range(1, n):
        if is_bullish_engulfing(o, h, l, c, i):
            bull[i] = "bullish_engulfing"
        elif is_hammer(o, h, l, c, i, wr, bm, om):
            bull[i] = "hammer"
        if is_bearish_engulfing(o, h, l, c, i):
            bear[i] = "bearish_engulfing"
        elif is_shooting_star(o, h, l, c, i, wr, bm, om):
            bear[i] = "shooting_star"
    return bull, bear


def trend_series(strat, mode: str) -> np.ndarray:
    """Per-base-bar allowed trend direction. mode='high' -> 1h only;
    'mid_high' -> 1h and 15m must agree."""
    t1 = strat.trend_1h.to_numpy()
    if mode == "high":
        return t1
    t15 = strat.trend_15.to_numpy()
    return np.where((t15 == "bull") & (t1 == "bull"), "bull",
                    np.where((t15 == "bear") & (t1 == "bear"), "bear", "none"))


def run_poi_lab(base: pd.DataFrame, cfg: Config, trend_mode: str,
                entry_mode: str = "touch"):
    """Return (trades, backtester). Each trade carries .same_color, .multi_tf,
    .gap_atr, .poi_tf and .pattern tags.

    entry_mode='touch'  : enter the moment price taps the zone (experiment 1).
    entry_mode='pattern': enter only when a trend-aligned 5m candle pattern
                          (engulfing / hammer / shooting-star) closes while
                          touching or inside the zone (experiment 2)."""
    cfg.require_same_color = False        # take every gap
    bt = Backtester(base, cfg)
    strat = bt.strategy
    trend = trend_series(strat, trend_mode)

    o = base["open"].to_numpy(float)
    h = base["high"].to_numpy(float)
    l = base["low"].to_numpy(float)
    c = base["close"].to_numpy(float)
    atr_arr = strat.atr.to_numpy(float)
    n = len(base)
    imbs = strat.imbalances

    bull_pat = bear_pat = None
    if entry_mode == "pattern":
        bull_pat, bear_pat = _precompute_patterns(o, h, l, c, cfg)

    # per-timeframe arrays for fast multi-TF overlap checks (same direction only)
    by_tf: dict[str, list] = {}
    for z in imbs:
        by_tf.setdefault(z.tf, []).append(z)
    tf_arr = {tf: (np.array([z.lower for z in zs]), np.array([z.upper for z in zs]),
                   np.array([z._meta["usable_from"] for z in zs]),
                   np.array([z.direction for z in zs]))
              for tf, zs in by_tf.items()}

    trades: list[Trade] = []
    for imb in imbs:
        d = imb.direction
        start = imb._meta["usable_from"]
        inv = min(imb._meta["invalid_from"], n)
        if start >= inv:
            continue
        near = imb.upper if d == "bull" else imb.lower
        far = imb.lower if d == "bull" else imb.upper

        # candidate bars: price overlaps the zone AND the trend is pro
        seg_l, seg_h, seg_t = l[start:inv], h[start:inv], trend[start:inv]
        touch_cond = (seg_l <= imb.upper) & (seg_h >= imb.lower) & (seg_t == d)
        if not touch_cond.any():
            continue
        cand = np.nonzero(touch_cond)[0] + start

        if entry_mode == "touch":
            entry_idx = int(cand[0])
            entry_price = near
            pat_name = "touch"
        else:
            pat_arr = bull_pat if d == "bull" else bear_pat
            entry_idx = None
            for gi in cand:                     # first pattern-while-touching
                pn = pat_arr[gi]
                if pn is None:
                    continue
                ep = c[gi]                      # enter at the pattern's close
                if (d == "bull" and ep > far) or (d == "bear" and ep < far):
                    entry_idx, entry_price, pat_name = int(gi), float(ep), pn
                    break
            if entry_idx is None:
                continue

        a = atr_arr[entry_idx]
        gap_atr = (imb.upper - imb.lower) / a if (np.isfinite(a) and a > 0) else None

        # multi-timeframe: overlaps a confirmed SAME-DIRECTION imbalance on
        # another timeframe (true nested confluence, e.g. 5m gap inside a 1h gap)
        mtf = False
        for tf2, (lows, ups, us, dirs) in tf_arr.items():
            if tf2 == imb.tf:
                continue
            if ((imb.lower < ups) & (lows < imb.upper) & (us <= entry_idx) & (dirs == d)).any():
                mtf = True
                break

        # touch-mode blow-through: the tap bar wicks clean through the far edge
        if (entry_mode == "touch"
                and ((d == "bull" and l[entry_idx] <= far) or (d == "bear" and h[entry_idx] >= far))):
            tr = Trade(direction=d, entry_index=entry_idx, entry_time=base.index[entry_idx],
                       entry_price=near, init_stop=far, risk=abs(near - far),
                       pattern="touch", poi_tf=imb.tf)
            tr.exit_index = entry_idx
            tr.exit_price = far
            tr.exit_reason = "blew_through"
            tr.r_multiple = -1.0
            tr.bars_held = 0
        else:
            sig = Signal(index=entry_idx, time=base.index[entry_idx], direction=d,
                         entry_price=entry_price, pattern=pat_name, poi=imb, nested_tf=imb.tf)
            tr = bt._simulate(sig, far, o=o, h=h, l=l, c=c, atr_arr=atr_arr, n=n)

        tr.same_color = imb.same_color          # type: ignore[attr-defined]
        tr.multi_tf = mtf                        # type: ignore[attr-defined]
        tr.gap_atr = gap_atr                     # type: ignore[attr-defined]
        tr.poi_tf = imb.tf
        trades.append(tr)

    trades.sort(key=lambda t: t.entry_index)
    return trades, bt


# --------------------------------------------------------------------------- #
# segmentation
# --------------------------------------------------------------------------- #
def _gap_bucket(t) -> Optional[str]:
    g = getattr(t, "gap_atr", None)
    if g is None or not np.isfinite(g):
        return None
    if g < 0.5:
        return "<0.5"
    if g < 1.0:
        return "0.5-1"
    if g < 2.0:
        return "1-2"
    return ">2"


PATTERNS = ["bullish_engulfing", "hammer", "bearish_engulfing", "shooting_star", "touch"]

SEGMENTS = {
    "POI timeframe": (lambda t: t.poi_tf, ["60min", "15min", "5min"]),
    "Candle pattern": (lambda t: t.pattern, PATTERNS),
    "Same colour?": (lambda t: "same" if t.same_color else "mixed", ["same", "mixed"]),
    "Multi-timeframe?": (lambda t: "multi-TF" if t.multi_tf else "single-TF", ["multi-TF", "single-TF"]),
    "Direction": (lambda t: t.direction, ["bull", "bear"]),
    "Gap size (ATR)": (_gap_bucket, ["<0.5", "0.5-1", "1-2", ">2"]),
}


def crosstab(trades, cfg, key1, order1, key2, order2):
    """rows (key1) x cols (key2) -> (expectancy, n) cells, only computing cells
    with enough trades to mean something."""
    cells = {}
    for k1 in order1:
        for k2 in order2:
            sub = [t for t in trades if key1(t) == k1 and key2(t) == k2]
            cells[(k1, k2)] = (compute_stats(sub, cfg)["expectancy_r"], len(sub)) if sub else (None, 0)
    return cells


def format_crosstab(title, cells, order1, order2) -> str:
    lines = [f"\n  {title}  (expectancy R / n)"]
    lines.append("    " + " " * 18 + "".join(f"{k2:>18}" for k2 in order2))
    for k1 in order1:
        row = [f"{(f'{e:+.3f}/{nn}' if e is not None else '—'):>18}"
               for (e, nn) in (cells[(k1, k2)] for k2 in order2)]
        lines.append(f"    {k1:18}" + "".join(row))
    return "\n".join(lines)


def segment(trades, cfg: Config, keyfn, order):
    groups: dict = {}
    for t in trades:
        k = keyfn(t)
        if k is None:
            continue
        groups.setdefault(k, []).append(t)
    rows = []
    keys = [k for k in order if k in groups] + [k for k in groups if k not in order]
    for k in keys:
        rows.append((k, compute_stats(groups[k], cfg)))
    return rows


def two_way(trades, cfg: Config):
    """same-colour x multi-TF expectancy grid (the headline question)."""
    grid = {}
    for sc in ("same", "mixed"):
        for mt in ("multi-TF", "single-TF"):
            sub = [t for t in trades
                   if ("same" if t.same_color else "mixed") == sc
                   and ("multi-TF" if t.multi_tf else "single-TF") == mt]
            grid[(sc, mt)] = compute_stats(sub, cfg) if sub else {"trades": 0}
    return grid


# --------------------------------------------------------------------------- #
# console output
# --------------------------------------------------------------------------- #
def _statline(name, s) -> str:
    if not s.get("trades"):
        return f"    {name:12} n=0"
    return (f"    {name:12} n={s['trades']:<5d} win={s['win_rate']*100:4.1f}%  "
            f"exp={s['expectancy_r']:+.3f}R  PF={s['profit_factor']:.2f}  "
            f"total={s['total_r']:+6.1f}R  avgW={s['avg_win_r']:+.2f} avgL={s['avg_loss_r']:+.2f}")


def format_lab(trades, cfg: Config, trend_mode: str, meta: dict) -> str:
    lines = [f"\n  TREND = {('1h only' if trend_mode=='high' else '1h + 15m')}"
             f"   ({len(trades)} POI trades)"]
    lines.append("  " + "-" * 96)
    lines.append(_statline("OVERALL", compute_stats(trades, cfg)))
    for title, (keyfn, order) in SEGMENTS.items():
        lines.append(f"\n  by {title}")
        for k, s in segment(trades, cfg, keyfn, order):
            lines.append(_statline(str(k), s))
    lines.append("\n  same-colour x multi-TF (expectancy R / n)")
    grid = two_way(trades, cfg)
    lines.append(f"    {'':10} {'multi-TF':>16} {'single-TF':>16}")
    for sc in ("same", "mixed"):
        cells = []
        for mt in ("multi-TF", "single-TF"):
            s = grid[(sc, mt)]
            cells.append(f"{s['expectancy_r']:+.3f}/{s['trades']}" if s.get("trades") else "—/0")
        lines.append(f"    {sc:10} {cells[0]:>16} {cells[1]:>16}")

    # pattern interactions (only meaningful once an entry pattern is required)
    if any(t.pattern != "touch" for t in trades):
        pats = [p for p in PATTERNS if p != "touch"]
        for title, k2, o2 in [
            ("pattern x POI timeframe", lambda t: t.poi_tf, ["60min", "15min", "5min"]),
            ("pattern x same-colour", lambda t: "same" if t.same_color else "mixed", ["same", "mixed"]),
            ("pattern x multi-TF", lambda t: "multi-TF" if t.multi_tf else "single-TF", ["multi-TF", "single-TF"]),
        ]:
            lines.append(format_crosstab(title, crosstab(trades, cfg, lambda t: t.pattern, pats, k2, o2),
                                         pats, o2))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# visual report
# --------------------------------------------------------------------------- #
def build_lab_report(results: dict, cfg: Config, meta: dict, source: str) -> str:
    from .report import _svg_bars, _PAGE, _card

    cards = []
    for mode, trades in results.items():
        s = compute_stats(trades, cfg)
        lbl = "1h" if mode == "high" else "1h+15m"
        cards.append(_card(f"{lbl} · expectancy",
                           f"{s['expectancy_r']:+.3f}R" if s.get("trades") else "—",
                           "pos" if s.get("expectancy_r", 0) > 0 else "neg"))
        cards.append(_card(f"{lbl} · trades / PF",
                           f"{s.get('trades',0)} / {s.get('profit_factor',0):.2f}"))
    cards_html = "".join(cards)

    sections = []
    for title, (keyfn, order) in SEGMENTS.items():
        for mode, trades in results.items():
            rows = segment(trades, cfg, keyfn, order)
            labels = [str(k) for k, _ in rows]
            vals = [round(s["expectancy_r"], 3) if s.get("trades") else 0.0 for _, s in rows]
            cols = ["#1f9d55" if v >= 0 else "#e3342f" for v in vals]
            lbl = "1h" if mode == "high" else "1h+15m"
            sections.append((f"{title} — expectancy (R) · trend {lbl}",
                             _svg_bars(vals, cols, labels=labels, fmt="{:+.2f}", label_every=1)))
    charts = "".join(f'<section class="panel"><h3>{t}</h3>{svg}</section>' for t, svg in sections)

    # detail tables
    tables = []
    for mode, trades in results.items():
        lbl = "1h only" if mode == "high" else "1h + 15m"
        trs = []
        for title, (keyfn, order) in SEGMENTS.items():
            trs.append(f"<tr><td class='l' colspan='7' style='color:#58a6ff'>by {title}</td></tr>")
            for k, s in segment(trades, cfg, keyfn, order):
                if not s.get("trades"):
                    continue
                ec = "pos" if s["expectancy_r"] > 0 else "neg"
                trs.append(
                    f"<tr><td class='l'>{k}</td><td>{s['trades']}</td>"
                    f"<td>{s['win_rate']*100:.1f}%</td><td class='{ec}'>{s['expectancy_r']:+.3f}</td>"
                    f"<td>{s['profit_factor']:.2f}</td><td>{s['total_r']:+.1f}</td>"
                    f"<td>{s['avg_win_r']:+.2f}/{s['avg_loss_r']:+.2f}</td></tr>")
        tables.append(
            f"<section class='panel'><h3>Detail — trend {lbl}</h3><div class='tw'><table>"
            f"<thead><tr><th class='l'>segment</th><th>n</th><th>win</th><th>exp R</th>"
            f"<th>PF</th><th>total R</th><th>avgW/L</th></tr></thead>"
            f"<tbody>{''.join(trs)}</tbody></table></div></section>")

    # refined-stack panels (net of 0.5pt slippage) — the punchline
    refined_html = ""
    if any(t.pattern != "touch" for mode_trades in results.values() for t in mode_trades):
        eng = lambda t: t.pattern in ("bullish_engulfing", "bearish_engulfing")
        stacks = [
            ("engulfing only", lambda t: eng(t)),
            ("+ same-colour", lambda t: eng(t) and t.same_color),
            ("+ single-TF", lambda t: eng(t) and not t.multi_tf),
            ("+ gap 0.5-1 ATR", lambda t: eng(t) and _gap_bucket(t) == "0.5-1"),
            ("+ same + gap 0.5-1", lambda t: eng(t) and t.same_color and _gap_bucket(t) == "0.5-1"),
        ]
        for mode, trades in results.items():
            lbl = "1h only" if mode == "high" else "1h + 15m"
            rows = []
            for name, f in stacks:
                ts = [t for t in trades if f(t)]
                e0, n = _exp_cost(ts, 0.0)
                e5, _ = _exp_cost(ts, 0.5)
                c0 = "pos" if e0 > 0 else "neg"
                c5 = "pos" if e5 > 0 else "neg"
                rows.append(f"<tr><td class='l'>{name}</td><td>{n}</td>"
                            f"<td class='{c0}'>{e0:+.3f}</td><td class='{c5}'>{e5:+.3f}</td></tr>")
            refined_html += (
                f"<section class='panel'><h3>Refined filter stack — trend {lbl} "
                f"(net of 0.5pt slippage)</h3><div class='tw'><table><thead><tr>"
                f"<th class='l'>filter</th><th>n</th><th>exp@0</th><th>exp@0.5pt</th>"
                f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>")

    tfs = f"{cfg.base_tf}/{cfg.mid_tf}/{cfg.high_tf}"
    entry_lbl = "5m pattern entry" if meta.get("entry") == "pattern" else "touch entry"
    subtitle = (f"POI lab · every gap, {entry_lbl} pro-trend, stop=far edge, ATR trail · "
                f"{tfs} · {meta.get('start','?')} → {meta.get('end','?')} · "
                f"{meta.get('n_base','?')} bars · {source}")
    body = f"<section class='cards'>{cards_html}</section>{charts}{refined_html}{''.join(tables)}"
    return _PAGE.format(title=f"{cfg.symbol} · POI lab", subtitle=subtitle, body=body)


def _exp_cost(ts, pts):
    if not ts:
        return float("nan"), 0
    r = np.array([t.r_multiple for t in ts], dtype=float)
    risk = np.array([t.risk for t in ts], dtype=float)
    adj = r - np.where(risk > 0, pts / risk, 0.0)
    return float(adj.mean()), len(ts)


def refined(trades, cfg) -> str:
    """Stack the properties that looked best one-way and re-measure, net of a
    realistic 0.5-pt round-trip slippage, to see if a real edge survives."""
    eng = lambda t: t.pattern in ("bullish_engulfing", "bearish_engulfing")
    filters = [
        ("engulfing only", lambda t: eng(t)),
        ("engulfing + same-colour", lambda t: eng(t) and t.same_color),
        ("engulfing + single-TF", lambda t: eng(t) and not t.multi_tf),
        ("engulfing + gap 0.5-1 ATR", lambda t: eng(t) and _gap_bucket(t) == "0.5-1"),
        ("engulfing + same + gap 0.5-1", lambda t: eng(t) and t.same_color and _gap_bucket(t) == "0.5-1"),
        ("engulfing + same + single-TF", lambda t: eng(t) and t.same_color and not t.multi_tf),
    ]
    lines = ["  Refined filter stack — expectancy@0 / @0.5pt cost / n  (watch small n!)"]
    for name, f in filters:
        ts = [t for t in trades if f(t)]
        e0, n = _exp_cost(ts, 0.0)
        e5, _ = _exp_cost(ts, 0.5)
        lines.append(f"    {name:32} {e0:+.3f} / {e5:+.3f} / {n}")
    return "\n".join(lines)


def cost_robustness(trades, levels=(0.0, 0.25, 0.5, 0.75, 1.0)) -> str:
    """Expectancy of each timeframe source as a fixed price slippage (ES points,
    round-trip) is charged. Cost in R = points / stop-size, so a tiny 5m stop is
    punished far harder than a wide 1h stop. This disentangles 'which timeframe'
    from 'which has the tightest stop'."""
    groups = {
        "5m only": [t for t in trades if t.poi_tf == "5min"],
        "15m only": [t for t in trades if t.poi_tf == "15min"],
        "1h only": [t for t in trades if t.poi_tf == "60min"],
        "5m + 15m": [t for t in trades if t.poi_tf in ("5min", "15min")],
        "5m+15m+1h": list(trades),
    }
    lines = ["  Cost-robustness by POI source — expectancy R vs ES-points round-trip slippage",
             "  (cost in R = points / stop size; t-stat tests edge != 0 at zero cost)"]
    cols = "  ".join(f"{(str(p)+'pt' if p else 'pts=0'):>7}" for p in levels)
    hdr = f"  {'source':11} {'n':>5} {'medStop':>7} {'t-stat':>6}  {cols}"
    lines.append(hdr)
    lines.append("  " + "-" * (len(hdr) - 2))
    for name, ts in groups.items():
        if not ts:
            continue
        r = np.array([t.r_multiple for t in ts], dtype=float)
        risk = np.array([t.risk for t in ts], dtype=float)
        n = len(ts)
        std = r.std(ddof=1) if n > 1 else float("nan")
        tstat = r.mean() / (std / np.sqrt(n)) if (n > 1 and std > 0) else float("nan")
        cells = []
        for pts in levels:
            adj = r - np.where(risk > 0, pts / risk, 0.0)
            cells.append(f"{adj.mean():+7.3f}")
        lines.append(f"  {name:11} {n:5d} {np.median(risk):7.2f} {tstat:6.1f}  " + "  ".join(cells))
    lines.append("\n  medStop = median stop distance in ES points (= 1R in price)")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="POI laboratory (experiment 1)")
    p.add_argument("--symbol", default="ES=F")
    p.add_argument("--preset", choices=list(Config.PRESETS), default="intraday")
    p.add_argument("--entry", choices=["touch", "pattern"], default="touch",
                   help="touch = enter on tap (exp 1); pattern = require a 5m candle pattern (exp 2)")
    p.add_argument("--report", metavar="PATH")
    p.add_argument("--synthetic", action="store_true")
    args = p.parse_args(argv)

    cfg = Config.preset(args.preset, symbol=args.symbol)
    source = "yahoo"
    if args.synthetic:
        base = synthetic_series(n=4000)
        cfg.symbol = "SYNTH"
        source = "synthetic"
    else:
        try:
            base = load_base(cfg)
        except Exception as e:  # noqa: BLE001
            print(f"data load failed ({e}); using synthetic", flush=True)
            base = synthetic_series(n=4000)
            cfg.symbol = "SYNTH"
            source = "synthetic"

    meta = {"start": base.index[0].date(), "end": base.index[-1].date(),
            "n_base": len(base), "entry": args.entry}
    exp = "2 (POI + 5m pattern)" if args.entry == "pattern" else "1 (POI touch)"
    print(f"\nPOI lab — experiment {exp} — {cfg.symbol} · "
          f"{cfg.base_tf}/{cfg.mid_tf}/{cfg.high_tf} · {meta['start']} → {meta['end']} "
          f"· {len(base)} bars")
    print("=" * 100)

    results = {}
    for mode in ("high", "mid_high"):
        trades, _ = run_poi_lab(base, Config.preset(args.preset, symbol=cfg.symbol),
                                mode, entry_mode=args.entry)
        results[mode] = trades
        print(format_lab(trades, cfg, mode, meta))
        print("\n" + cost_robustness(trades))
        if args.entry == "pattern":
            print("\n" + refined(trades, cfg))

    if args.report:
        with open(args.report, "w") as f:
            f.write(build_lab_report(results, cfg, meta, source))
        print(f"\nWrote visual POI lab -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
