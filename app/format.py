"""Display formatting helpers. Kept separate and pure so the percent-change
edge cases (zero, null, sign flip) are unit-testable (SPEC 15)."""
from __future__ import annotations

import datetime as dt


def pct_change(newer: float | None, older: float | None) -> float | None:
    """(newer - older) / abs(older); None when the older value is 0 or
    missing. Sign flips produce large magnitudes — rendered anyway (SPEC 9.3)."""
    if newer is None or older is None or older == 0:
        return None
    return (newer - older) / abs(older)


def fmt_millions(value: float | None) -> str:
    """USD value -> millions with thousands separators, negatives in parens."""
    if value is None:
        return "-"
    millions = value / 1e6
    return f"({abs(millions):,.0f})" if millions < 0 else f"{millions:,.0f}"


def fmt_pct(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value * 100:,.{decimals}f}%"


def fmt_ratio(value: float | None, fmt: str) -> str:
    """Render a ratio per its display-format hint."""
    if value is None:
        return "n/a"
    if fmt == "percent":
        return fmt_pct(value)
    if fmt == "x":
        return f"{value:,.2f}x"
    if fmt == "days":
        return f"{value:,.1f}"
    if fmt == "usd":
        return f"({abs(value):,.2f})" if value < 0 else f"{value:,.2f}"
    if fmt == "usd_m":
        return fmt_millions(value)
    return f"{value:,.2f}"


def fmt_statement_value(value: float | None, unit: str) -> str:
    """Statement cells: USD and share counts in millions; per-share as-is."""
    if value is None:
        return "-"
    if unit == "USD/shares":
        return f"({abs(value):,.2f})" if value < 0 else f"{value:,.2f}"
    return fmt_millions(value)


def fmt_date(value: dt.date | dt.datetime | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M UTC")
    return value.isoformat()
