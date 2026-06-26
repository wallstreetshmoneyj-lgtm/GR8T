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


def trend_series(strat, mode: str) -> np.ndarray:
    """Per-base-bar allowed trend direction. mode='high' -> 1h only;
    'mid_high' -> 1h and 15m must agree."""
    t1 = strat.trend_1h.to_numpy()
    if mode == "high":
        return t1
    t15 = strat.trend_15.to_numpy()
    return np.where((t15 == "bull") & (t1 == "bull"), "bull",
                    np.where((t15 == "bear") & (t1 == "bear"), "bear", "none"))


def run_poi_lab(base: pd.DataFrame, cfg: Config, trend_mode: str):
    """Return (trades, backtester). Each trade carries .same_color, .multi_tf,
    .gap_atr, .poi_tf tags."""
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
        seg_l, seg_h, seg_t = l[start:inv], h[start:inv], trend[start:inv]
        cond = (seg_l <= imb.upper) & (seg_h >= imb.lower) & (seg_t == d)
        if not cond.any():
            continue
        touch = start + int(cond.argmax())

        near = imb.upper if d == "bull" else imb.lower
        far = imb.lower if d == "bull" else imb.upper
        a = atr_arr[touch]
        gap_atr = (imb.upper - imb.lower) / a if (np.isfinite(a) and a > 0) else None

        # multi-timeframe: overlaps a confirmed SAME-DIRECTION imbalance on
        # another timeframe (true nested confluence, e.g. 5m gap inside a 1h gap)
        mtf = False
        for tf2, (lows, ups, us, dirs) in tf_arr.items():
            if tf2 == imb.tf:
                continue
            if ((imb.lower < ups) & (lows < imb.upper) & (us <= touch) & (dirs == d)).any():
                mtf = True
                break

        # blow-through: the tap bar wicks clean through to the far edge -> -1R
        if (d == "bull" and l[touch] <= far) or (d == "bear" and h[touch] >= far):
            tr = Trade(direction=d, entry_index=touch, entry_time=base.index[touch],
                       entry_price=near, init_stop=far, risk=abs(near - far),
                       pattern="touch", poi_tf=imb.tf)
            tr.exit_index = touch
            tr.exit_price = far
            tr.exit_reason = "blew_through"
            tr.r_multiple = -1.0
            tr.bars_held = 0
        else:
            sig = Signal(index=touch, time=base.index[touch], direction=d,
                         entry_price=near, pattern="touch", poi=imb, nested_tf=imb.tf)
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


SEGMENTS = {
    "POI timeframe": (lambda t: t.poi_tf, ["60min", "15min", "5min"]),
    "Same colour?": (lambda t: "same" if t.same_color else "mixed", ["same", "mixed"]),
    "Multi-timeframe?": (lambda t: "multi-TF" if t.multi_tf else "single-TF", ["multi-TF", "single-TF"]),
    "Direction": (lambda t: t.direction, ["bull", "bear"]),
    "Gap size (ATR)": (_gap_bucket, ["<0.5", "0.5-1", "1-2", ">2"]),
}


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

    tfs = f"{cfg.base_tf}/{cfg.mid_tf}/{cfg.high_tf}"
    subtitle = (f"POI lab · every gap, touch-entry pro-trend, stop=far edge, ATR trail · "
                f"{tfs} · {meta.get('start','?')} → {meta.get('end','?')} · "
                f"{meta.get('n_base','?')} bars · {source}")
    body = f"<section class='cards'>{cards_html}</section>{charts}{''.join(tables)}"
    return _PAGE.format(title=f"{cfg.symbol} · POI lab", subtitle=subtitle, body=body)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="POI laboratory (experiment 1)")
    p.add_argument("--symbol", default="ES=F")
    p.add_argument("--preset", choices=list(Config.PRESETS), default="intraday")
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

    meta = {"start": base.index[0].date(), "end": base.index[-1].date(), "n_base": len(base)}
    print(f"\nPOI lab — {cfg.symbol} · {cfg.base_tf}/{cfg.mid_tf}/{cfg.high_tf} "
          f"· {meta['start']} → {meta['end']} · {len(base)} bars")
    print("=" * 100)

    results = {}
    for mode in ("high", "mid_high"):
        trades, _ = run_poi_lab(base, Config.preset(args.preset, symbol=cfg.symbol), mode)
        results[mode] = trades
        print(format_lab(trades, cfg, mode, meta))

    if args.report:
        with open(args.report, "w") as f:
            f.write(build_lab_report(results, cfg, meta, source))
        print(f"\nWrote visual POI lab -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
