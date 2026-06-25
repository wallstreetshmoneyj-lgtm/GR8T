"""Self-contained visual backtest report.

Renders a dark-themed HTML dashboard (stat cards + pure-SVG charts: equity
curve, drawdown, per-trade R, R distribution, monthly R, and a trades table)
from a BacktestResult. No JavaScript and no external dependencies, so the file
opens anywhere and can be shared as-is.
"""
from __future__ import annotations

import html
from typing import Optional, Sequence

from .config import Config
from .stats import compute_stats, stats_series


# --------------------------------------------------------------------------- #
# tiny SVG chart helpers
# --------------------------------------------------------------------------- #
_W, _H = 1000, 260          # logical viewBox size
_PADL, _PADR, _PADT, _PADB = 56, 16, 16, 28


def _scale(v, vmin, vmax, lo, hi):
    if vmax == vmin:
        return (lo + hi) / 2
    return lo + (v - vmin) / (vmax - vmin) * (hi - lo)


def _axis_labels(vmin, vmax, fmt="{:.0f}"):
    rows = []
    for frac in (0.0, 0.5, 1.0):
        val = vmin + (vmax - vmin) * frac
        y = _scale(val, vmin, vmax, _H - _PADB, _PADT)
        rows.append(
            f'<line x1="{_PADL}" y1="{y:.1f}" x2="{_W-_PADR}" y2="{y:.1f}" '
            f'class="grid"/><text x="{_PADL-6}" y="{y+3:.1f}" class="ylab">'
            f'{fmt.format(val)}</text>'
        )
    return "".join(rows)


def _svg_line(values: Sequence[float], *, area=True, color="#58a6ff",
              baseline: Optional[float] = None, fmt="{:.0f}") -> str:
    if not values:
        return '<div class="empty">no data</div>'
    vmin, vmax = min(values), max(values)
    if baseline is not None:
        vmin, vmax = min(vmin, baseline), max(vmax, baseline)
    pad = (vmax - vmin) * 0.08 or 1.0
    vmin, vmax = vmin - pad, vmax + pad
    n = len(values)
    xs = [_scale(i, 0, max(n - 1, 1), _PADL, _W - _PADR) for i in range(n)]
    ys = [_scale(v, vmin, vmax, _H - _PADB, _PADT) for v in values]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    out = [f'<svg viewBox="0 0 {_W} {_H}" class="chart-svg" preserveAspectRatio="none">']
    out.append(_axis_labels(vmin, vmax, fmt))
    if baseline is not None:
        by = _scale(baseline, vmin, vmax, _H - _PADB, _PADT)
        out.append(f'<line x1="{_PADL}" y1="{by:.1f}" x2="{_W-_PADR}" y2="{by:.1f}" class="zero"/>')
    if area:
        floor = _H - _PADB
        out.append(f'<polygon points="{xs[0]:.1f},{floor} {pts} {xs[-1]:.1f},{floor}" '
                   f'fill="{color}" fill-opacity="0.15"/>')
    out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
    out.append("</svg>")
    return "".join(out)


def _svg_underwater(values: Sequence[float], color="#e3342f") -> str:
    if not values:
        return '<div class="empty">no data</div>'
    vmin = min(min(values), 0.0)
    vmax = 0.0
    pad = (vmax - vmin) * 0.08 or 1.0
    lo, hi = vmin - pad, vmax + pad
    n = len(values)
    xs = [_scale(i, 0, max(n - 1, 1), _PADL, _W - _PADR) for i in range(n)]
    ys = [_scale(v, lo, hi, _H - _PADB, _PADT) for v in values]
    zero_y = _scale(0.0, lo, hi, _H - _PADB, _PADT)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    out = [f'<svg viewBox="0 0 {_W} {_H}" class="chart-svg" preserveAspectRatio="none">']
    out.append(_axis_labels(lo, hi, "{:.0f}%"))
    out.append(f'<polygon points="{xs[0]:.1f},{zero_y:.1f} {pts} {xs[-1]:.1f},{zero_y:.1f}" '
               f'fill="{color}" fill-opacity="0.22"/>')
    out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/>')
    out.append("</svg>")
    return "".join(out)


def _svg_bars(values: Sequence[float], colors: Sequence[str], *,
              labels: Optional[Sequence[str]] = None, fmt="{:.1f}",
              label_every: int = 1) -> str:
    if not values:
        return '<div class="empty">no trades</div>'
    vmin = min(min(values), 0.0)
    vmax = max(max(values), 0.0)
    pad = (vmax - vmin) * 0.08 or 1.0
    lo, hi = vmin - pad, vmax + pad
    n = len(values)
    zero_y = _scale(0.0, lo, hi, _H - _PADB, _PADT)
    span = (_W - _PADR - _PADL)
    bw = span / n
    out = [f'<svg viewBox="0 0 {_W} {_H}" class="chart-svg" preserveAspectRatio="none">']
    out.append(_axis_labels(lo, hi, fmt))
    for i, v in enumerate(values):
        x = _PADL + i * bw
        y = _scale(v, lo, hi, _H - _PADB, _PADT)
        top = min(y, zero_y)
        h = abs(y - zero_y)
        out.append(f'<rect x="{x+bw*0.1:.1f}" y="{top:.1f}" width="{bw*0.8:.1f}" '
                   f'height="{max(h,0.5):.1f}" fill="{colors[i]}"/>')
        if labels is not None and (i % label_every == 0):
            out.append(f'<text x="{x+bw/2:.1f}" y="{_H-8:.1f}" class="xlab">'
                       f'{html.escape(str(labels[i]))}</text>')
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------- #
# report assembly
# --------------------------------------------------------------------------- #
def _card(label: str, value: str, cls: str = "") -> str:
    return (f'<div class="card {cls}"><div class="card-v">{value}</div>'
            f'<div class="card-k">{html.escape(label)}</div></div>')


def _sign(x: float) -> str:
    return "pos" if x > 0 else "neg" if x < 0 else ""


def build_fragment(result, cfg: Config, *, include_table: bool = True) -> str:
    """Return the cards + SVG charts (and optionally the trades table) as an
    HTML fragment, reusable inside the web UI or the standalone report."""
    stats = compute_stats(result.trades, cfg)
    series = stats_series(result.trades, cfg)

    if not result.trades:
        return '<p class="empty">No trades were generated for these parameters.</p>'

    cards = "".join([
        _card("Trades", f"{stats['trades']}", ""),
        _card("Win rate", f"{stats['win_rate']*100:.1f}%",
              _sign(stats['win_rate'] - 0.5)),
        _card("Expectancy", f"{stats['expectancy_r']:+.3f} R",
              _sign(stats['expectancy_r'])),
        _card("Total", f"{stats['total_r']:+.2f} R", _sign(stats['total_r'])),
        _card("Profit factor",
              f"{stats['profit_factor']:.2f}" if stats['profit_factor'] != float('inf') else "∞",
              _sign(stats['profit_factor'] - 1)),
        _card("Payoff", f"{stats['payoff_ratio']:.2f}"
              if stats['payoff_ratio'] != float('inf') else "∞"),
        _card("Max DD", f"{stats['max_drawdown_pct']:.1f}%", "neg"),
        _card("Return", f"{stats['return_pct']:+.1f}%", _sign(stats['return_pct'])),
    ])

    per_r = [p["r"] for p in series["per_trade"]]
    per_col = ["#1f9d55" if x >= 0 else "#e3342f" for x in per_r]
    hist = series["histogram"]
    hist_centers = [f'{(hist["edges"][i]+hist["edges"][i+1])/2:+.1f}'
                    for i in range(len(hist["counts"]))]
    months = [m["month"][2:] for m in series["monthly"]]      # YY-MM
    month_r = [m["r"] for m in series["monthly"]]
    month_col = ["#1f9d55" if x >= 0 else "#e3342f" for x in month_r]
    m_every = max(1, len(months) // 16)
    t_every = max(1, len(per_r) // 24)

    charts = [
        ("Equity curve", _svg_line(series["equity"], color="#58a6ff",
                                    baseline=cfg.starting_equity, fmt="${:,.0f}")),
        ("Drawdown (underwater)", _svg_underwater(series["drawdown"])),
        ("R per trade", _svg_bars(per_r, per_col, fmt="{:+.0f}",
                                  labels=[str(p["n"]) for p in series["per_trade"]],
                                  label_every=t_every)),
        ("R-multiple distribution", _svg_bars(
            [float(c) for c in hist["counts"]], hist["colors"],
            labels=hist_centers, fmt="{:.0f}", label_every=1)),
        ("Monthly R", _svg_bars(month_r, month_col, labels=months,
                                fmt="{:+.0f}", label_every=m_every)),
    ]
    chart_html = "".join(
        f'<section class="panel"><h3>{html.escape(t)}</h3>{svg}</section>'
        for t, svg in charts
    )

    table_html = ""
    if include_table:
        rows = []
        for i, t in enumerate(result.trades):
            rc = "pos" if t.r_multiple > 0 else "neg"
            dc = "bull" if t.direction == "bull" else "bear"
            rows.append(
                f'<tr><td>{i+1}</td><td class="l">{series["per_trade"][i]["exit_time"]}</td>'
                f'<td class="{dc} l">{"LONG" if t.direction=="bull" else "SHORT"}</td>'
                f'<td class="l">{html.escape(t.pattern.replace("_"," "))}</td>'
                f'<td>{t.poi_tf}</td><td>{t.entry_price:.2f}</td><td>{t.init_stop:.2f}</td>'
                f'<td>{t.exit_price:.2f}</td><td class="{rc}">{t.r_multiple:+.2f}</td>'
                f'<td class="l">{t.exit_reason}</td></tr>'
            )
        n = len(result.trades)
        table_html = (
            f'<section class="panel"><h3>Trades ({n})</h3><div class="tw">'
            '<table><thead><tr><th>#</th><th class="l">Exit</th>'
            '<th class="l">Dir</th><th class="l">Pattern</th><th>TF</th>'
            '<th>Entry</th><th>Stop</th><th>Exit</th><th>R</th>'
            '<th class="l">Why</th></tr></thead><tbody>'
            + "".join(rows) +
            "</tbody></table></div></section>"
        )

    return (f'<section class="cards">{cards}</section>{chart_html}{table_html}')


def build_report(result, cfg: Config, *, source: str = "yahoo",
                 meta: Optional[dict] = None) -> str:
    """Full standalone HTML page wrapping the chart fragment."""
    meta = meta or {}
    if not result.trades:
        body = '<p class="empty">No trades were generated for these parameters.</p>'
        return _PAGE.format(title=cfg.symbol, subtitle="", body=body)
    tfs = f"{cfg.base_tf}/{cfg.mid_tf}/{cfg.high_tf}"
    span = f"{meta.get('start','?')} → {meta.get('end','?')}"
    subtitle = (f"{tfs} · {span} · {meta.get('n_base','?')} base bars · "
                f"source: {html.escape(str(source))}")
    body = build_fragment(result, cfg, include_table=True)
    return _PAGE.format(title=html.escape(cfg.symbol),
                        subtitle=html.escape(subtitle), body=body)


_PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>
:root{{--bg:#0d1117;--panel:#161b22;--bd:#2a3240;--tx:#e6edf3;--mut:#8b97a7;
--grn:#1f9d55;--red:#e3342f;--acc:#58a6ff}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font:14px -apple-system,Segoe UI,Roboto,sans-serif;padding:20px;max-width:1100px;margin:0 auto}}
h1{{font-size:22px}} h3{{font-size:14px;margin-bottom:8px;color:var(--tx)}}
.sub{{color:var(--mut);font-size:12.5px;margin:4px 0 18px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:18px}}
.card{{background:var(--panel);border:1px solid var(--bd);border-radius:10px;padding:12px 14px}}
.card-v{{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}}
.card-k{{color:var(--mut);font-size:11.5px;margin-top:2px;text-transform:uppercase;letter-spacing:.4px}}
.card.pos .card-v{{color:var(--grn)}} .card.neg .card-v{{color:var(--red)}}
.panel{{background:var(--panel);border:1px solid var(--bd);border-radius:10px;padding:14px;margin-bottom:16px}}
.chart-svg{{width:100%;height:240px;display:block}}
.grid{{stroke:#1c2430;stroke-width:1}} .zero{{stroke:#3a4452;stroke-width:1;stroke-dasharray:4 3}}
.ylab{{fill:var(--mut);font-size:11px;text-anchor:end}}
.xlab{{fill:var(--mut);font-size:10px;text-anchor:middle}}
.empty{{color:var(--mut);padding:20px;text-align:center}}
.tw{{overflow-x:auto}} table{{width:100%;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums}}
th,td{{padding:5px 8px;text-align:right;border-bottom:1px solid var(--bd);white-space:nowrap}}
th.l,td.l{{text-align:left}} th{{color:var(--mut);font-weight:600}}
td.pos{{color:var(--grn);font-weight:700}} td.neg{{color:var(--red);font-weight:700}}
td.bull{{color:var(--grn)}} td.bear{{color:var(--red)}}
@media(max-width:720px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body>
<h1>GR8T backtest — {title}</h1><div class="sub">{subtitle}</div>
{body}
<div class="sub" style="margin-top:18px">Generated by GR8T · for research and education, not financial advice.</div>
</body></html>"""
