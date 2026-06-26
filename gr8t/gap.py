"""GR8T Gap-Continuation — a from-scratch intraday strategy.

Premise (validated on the data, not borrowed from SMC lore): the direction of
the overnight move tends to CONTINUE through the next cash session, and the
effect is concentrated in larger gaps. So:

  * Signal : overnight gap = open(09:30 ET) / prev close(16:00 ET) - 1
  * Filter : only trade when |gap| >= threshold (default 20 bps) — small gaps are
             noise, big gaps carry information/flow
  * Trade  : at the open, go LONG if gapped up, SHORT if gapped down
  * Exit   : the cash close (one trade/day) — optional intraday stop caps tails
  * Why it is robust: it is self-regime-adapting — it is automatically short in
    down-gapping bear markets and long in up-gapping bull markets, so it has no
    structural long bias (the flaw that sank the SMC strategy).

One trade per day means costs are a tiny fraction of the open->close move, which
is the whole point after we learned tight-stop scalping can't clear slippage.

    python -m gr8t.gap --start 2012-01 --end 2018-12 --report gap.html
"""
from __future__ import annotations

import argparse
import numpy as np
import pandas as pd

from .config import Config
from .data import load_github, synthetic_series


# --------------------------------------------------------------------------- #
# per-day session features (no look-ahead: gap is known at the open)
# --------------------------------------------------------------------------- #
def session_table(base: pd.DataFrame, open_t="09:30", close_t="15:55") -> pd.DataFrame:
    def at(day, t, col):
        x = day.at_time(t)
        return x[col].iloc[0] if len(x) else np.nan

    rows = []
    for date, day in base.groupby(base.index.date):
        rows.append((pd.Timestamp(date), at(day, open_t, "open"), at(day, close_t, "close")))
    f = pd.DataFrame(rows, columns=["date", "open", "close"]).dropna().reset_index(drop=True)
    f["prev_close"] = f["close"].shift(1)
    f["day_gap"] = (f["date"] - f["date"].shift(1)).dt.days
    f = f[(f["day_gap"] >= 1) & (f["day_gap"] <= 4)].dropna().reset_index(drop=True)
    f["gap"] = f["open"] / f["prev_close"] - 1.0
    f["intraday"] = f["close"] / f["open"] - 1.0
    return f


def _stop_exit(base: pd.DataFrame, date, direction, entry_px, stop_frac):
    """Return the realised intraday return if an intraday stop is hit, else None
    (hold to close). Walks the day's 5m bars in order — no look-ahead."""
    day = base[base.index.date == date]
    sess = day.between_time("09:30", "16:00")
    stop_px = entry_px * (1 - stop_frac) if direction > 0 else entry_px * (1 + stop_frac)
    for _, bar in sess.iterrows():
        if direction > 0 and bar["low"] <= stop_px:
            return -stop_frac
        if direction < 0 and bar["high"] >= stop_px:
            return -stop_frac
    return None


# --------------------------------------------------------------------------- #
# backtest
# --------------------------------------------------------------------------- #
def backtest(base: pd.DataFrame, threshold=0.0020, cost_pts=0.5, stop_frac=None):
    f = session_table(base)
    pos = np.where(f["gap"].abs() >= threshold, np.sign(f["gap"]), 0.0)
    rets = []
    for i, row in f.iterrows():
        d = pos[i]
        if d == 0:
            rets.append(0.0)
            continue
        r = None
        if stop_frac:
            r = _stop_exit(base, row["date"].date(), d, row["open"], stop_frac)
        if r is None:
            r = d * row["intraday"]
        r -= cost_pts / row["open"]            # one round-trip
        rets.append(r)
    f = f.assign(position=pos, ret=rets)
    f["equity"] = (1 + f["ret"]).cumprod()
    return f


def stats(f: pd.DataFrame) -> dict:
    traded = f[f["position"] != 0]
    r = traded["ret"].to_numpy()
    if len(r) == 0:
        return {"trades": 0}
    eq = (1 + traded["ret"]).cumprod().to_numpy()
    peak = np.maximum.accumulate(eq)
    maxdd = float((1 - eq / peak).max() * 100)
    wins = r[r > 0]; losses = r[r <= 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")
    years = max((f["date"].iloc[-1] - f["date"].iloc[0]).days / 365.25, 1e-9)
    cagr = (f["equity"].iloc[-1]) ** (1 / years) - 1
    return {
        "trades": int(len(r)),
        "days": int(len(f)),
        "win_rate": float((r > 0).mean() * 100),
        "mean_bps": float(r.mean() * 1e4),
        "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0,
        "total_return_pct": float((f["equity"].iloc[-1] - 1) * 100),
        "cagr_pct": float(cagr * 100),
        "max_dd_pct": maxdd,
        "profit_factor": float(pf),
        "avg_win_bps": float(wins.mean() * 1e4) if len(wins) else 0.0,
        "avg_loss_bps": float(losses.mean() * 1e4) if len(losses) else 0.0,
        "exposure_pct": float((f["position"] != 0).mean() * 100),
    }


def by_year(f: pd.DataFrame) -> pd.DataFrame:
    g = f.assign(year=f["date"].dt.year).groupby("year")
    out = g.apply(lambda d: pd.Series({
        "trades": int((d["position"] != 0).sum()),
        "ret_pct": (np.prod(1 + d["ret"]) - 1) * 100,
        "win%": (d.loc[d["position"] != 0, "ret"] > 0).mean() * 100 if (d["position"] != 0).any() else np.nan,
    }), include_groups=False)
    return out


def fmt_stats(s: dict) -> str:
    if not s.get("trades"):
        return "  no trades"
    rows = [
        ("Days / trades", f"{s['days']} / {s['trades']}  ({s['exposure_pct']:.0f}% exposure)"),
        ("Win rate", f"{s['win_rate']:.1f}%"),
        ("Mean / trade", f"{s['mean_bps']:+.2f} bps"),
        ("Sharpe (ann.)", f"{s['sharpe']:.2f}"),
        ("Total return", f"{s['total_return_pct']:+.1f}%"),
        ("CAGR", f"{s['cagr_pct']:+.1f}%"),
        ("Max drawdown", f"{s['max_dd_pct']:.1f}%"),
        ("Profit factor", f"{s['profit_factor']:.2f}"),
        ("Avg win / loss", f"{s['avg_win_bps']:+.1f} / {s['avg_loss_bps']:+.1f} bps"),
    ]
    w = max(len(k) for k, _ in rows)
    return "\n".join(f"  {k.ljust(w)} : {v}" for k, v in rows)


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def build_report(f, s, yr, cfg_symbol, meta, source) -> str:
    from .report import _svg_line, _svg_bars, _PAGE, _card

    sign = lambda x: "pos" if x > 0 else "neg"
    cards = [
        _card("Sharpe (ann.)", f"{s['sharpe']:.2f}", sign(s["sharpe"] - 0.5)),
        _card("CAGR", f"{s['cagr_pct']:+.1f}%", sign(s["cagr_pct"])),
        _card("Max drawdown", f"{s['max_dd_pct']:.1f}%", "neg"),
        _card("Win rate", f"{s['win_rate']:.1f}%"),
        _card("Profit factor", f"{s['profit_factor']:.2f}", sign(s["profit_factor"] - 1)),
        _card("Trades", f"{s['trades']}"),
        _card("Mean / trade", f"{s['mean_bps']:+.1f} bps", sign(s["mean_bps"])),
        _card("Total return", f"{s['total_return_pct']:+.0f}%", sign(s["total_return_pct"])),
    ]
    eq = [round(float(x), 4) for x in f["equity"].to_numpy()]
    yrs = [str(int(y)) for y in yr.index]
    yret = [round(float(x), 1) for x in yr["ret_pct"].to_numpy()]
    sections = [
        ("Equity curve (1 = start, compounded)", _svg_line(eq, color="#58a6ff", baseline=1.0, fmt="{:.2f}")),
        ("Return % by year", _svg_bars(yret, ["#1f9d55" if v >= 0 else "#e3342f" for v in yret],
                                       labels=yrs, fmt="{:+.0f}", label_every=1)),
    ]
    charts = "".join(f"<section class='panel'><h3>{t}</h3>{svg}</section>" for t, svg in sections)
    yr_rows = "".join(
        f"<tr><td class='l'>{int(y)}</td><td>{int(r['trades'])}</td>"
        f"<td class='{'pos' if r['ret_pct']>0 else 'neg'}'>{r['ret_pct']:+.1f}%</td>"
        f"<td>{r['win%']:.0f}%</td></tr>" for y, r in yr.iterrows())
    table = (f"<section class='panel'><h3>Year by year</h3><div class='tw'><table><thead><tr>"
             f"<th class='l'>year</th><th>trades</th><th>return</th><th>win</th></tr></thead>"
             f"<tbody>{yr_rows}</tbody></table></div></section>")
    subtitle = (f"gap-continuation intraday · enter at open in gap direction (|gap|>=20bps), "
                f"exit at close · {meta['start']} → {meta['end']} · {meta['n']} days · {source}")
    body = f"<section class='cards'>{''.join(cards)}</section>{charts}{table}"
    return _PAGE.format(title=f"{cfg_symbol} · gap-continuation", subtitle=subtitle, body=body)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Gap-continuation intraday strategy")
    p.add_argument("--symbol", default="SPX500")
    p.add_argument("--start", default="2012-01")
    p.add_argument("--end", default="2018-12")
    p.add_argument("--threshold-bps", type=float, default=20.0)
    p.add_argument("--cost-pts", type=float, default=0.5)
    p.add_argument("--stop-pct", type=float, default=None, help="optional intraday stop, e.g. 0.5")
    p.add_argument("--report", metavar="PATH")
    p.add_argument("--synthetic", action="store_true")
    args = p.parse_args(argv)

    if args.synthetic:
        base = synthetic_series(n=8000); source = "synthetic"
    else:
        base = load_github(args.symbol, args.start, args.end); source = "github OANDA 1m"

    f = backtest(base, threshold=args.threshold_bps / 1e4, cost_pts=args.cost_pts,
                 stop_frac=(args.stop_pct / 100 if args.stop_pct else None))
    s = stats(f)
    yr = by_year(f)
    meta = {"start": str(base.index[0].date()), "end": str(base.index[-1].date()), "n": len(f)}

    print(f"\nGR8T Gap-Continuation — {args.symbol} · |gap|>={args.threshold_bps:.0f}bps · "
          f"cost {args.cost_pts}pt" + (f" · stop {args.stop_pct}%" if args.stop_pct else ""))
    print(f"{meta['start']} → {meta['end']}")
    print("=" * 60)
    print(fmt_stats(s))
    print("\n  Year by year:")
    print(yr.to_string())

    if args.report:
        with open(args.report, "w") as fh:
            fh.write(build_report(f, s, yr, args.symbol, meta, source))
        print(f"\nWrote visual report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
